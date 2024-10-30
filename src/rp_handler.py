import base64
import json
import os
import time
import urllib.parse
import urllib.request
from io import BytesIO
from typing import List, Optional, Union

import requests
import runpod
from boto3 import session
from botocore.config import Config
from pydantic import BaseModel, Field, ValidationError
from requests_toolbelt import MultipartEncoder
from requests_toolbelt.multipart.encoder import FileFromURLWrapper
from runpod.serverless.utils import rp_upload

from .job import ComfyFileUrlInput, ComfyImageInput, ComfyOutput, ComfyWorkflow
from .supabase import SupabaseJobTrigger
from .trigger import create_trigger_handler

# Time to wait between API check attempts in milliseconds
COMFY_API_AVAILABLE_INTERVAL_MS = 50
# Maximum number of API check attempts
COMFY_API_AVAILABLE_MAX_RETRIES = 500
# Time to wait between poll attempts in milliseconds
COMFY_POLLING_INTERVAL_MS = os.environ.get("COMFY_POLLING_INTERVAL_MS", 250)
# Maximum number of poll attempts
COMFY_POLLING_MAX_RETRIES = os.environ.get("COMFY_POLLING_MAX_RETRIES", 5000)
# Host where ComfyUI is running
COMFY_HOST = "127.0.0.1:8188"
# Enforce a clean state after each job is done
# see https://docs.runpod.io/docs/handler-additional-controls#refresh-worker
REFRESH_WORKER = os.environ.get("REFRESH_WORKER", "false").lower() == "true"


class ComfyWorkerJob(BaseModel):
    "Define the input for the worker job"

    id: str = Field(..., description="The job id")
    workflow: ComfyWorkflow = Field(..., description="The workflow to run")
    images: Optional[List[ComfyImageInput]] = Field(default=None, description="The images to use")
    file_urls: Optional[List[ComfyFileUrlInput]] = Field(default=None, description="The file urls to use")
    output: Optional[ComfyOutput] = Field(default=None, description="The output configuration")
    trigger: Optional[Union[SupabaseJobTrigger]] = Field(
        default=None, description="The trigger configuration", discriminator="service"
    )


def validate_input(job_input):
    """
    Deprecated. Use pydantic model for input validation.

    Validates the input for the handler function.

    Args:
        job_input (dict): The input data to validate.

    Returns:
        tuple: A tuple containing the validated data and an error message, if any.
               The structure is (validated_data, error_message).
    """
    # Validate if job_input is provided
    if job_input is None:
        return None, "Please provide input"

    # Check if input is a string and try to parse it as JSON
    if isinstance(job_input, str):
        try:
            job_input = json.loads(job_input)
        except json.JSONDecodeError:
            return None, "Invalid JSON format in input"

    # Validate 'workflow' in input
    workflow = job_input.get("workflow")
    if workflow is None:
        return None, "Missing 'workflow' parameter"

    # Validate 'images' in input, if provided
    images = job_input.get("images")
    if images is not None:
        if not isinstance(images, list) or not all("name" in image and "image" in image for image in images):
            return (
                None,
                "'images' must be a list of objects with 'name' and 'image' keys",
            )

    # Validate 'file_urls' in input, if provided
    file_urls = job_input.get("file_urls")
    if file_urls is not None:
        if not isinstance(file_urls, list) or not all(
            "name" in file_url and "url" in file_url for file_url in file_urls
        ):
            return (
                None,
                "'file_urls' must be a list of objects with 'name' and 'url' keys",
            )
    # Validate 'output' in input, if provided
    output = job_input.get("output")
    if output is not None:
        if not isinstance(output, dict) or not (
            "type" in output and "bucket" in output and "endpoint_url" in output and "key_prefix" in output
        ):
            return (
                None,
                "'output' must be a dictionary with 'type', 'bucket', 'endpoint_url' and 'key_prefix' keys",
            )

    # Return validated data and no error
    return {
        "workflow": workflow,
        "images": images,
        "file_urls": file_urls,
        "output": output,
    }, None


def check_server(url, retries=500, delay=50):
    """
    Check if a server is reachable via HTTP GET request

    Args:
    - url (str): The URL to check
    - retries (int, optional): The number of times to attempt connecting to the server. Default is 50
    - delay (int, optional): The time in milliseconds to wait between retries. Default is 500

    Returns:
    bool: True if the server is reachable within the given number of retries, otherwise False
    """
    for i in range(retries):
        try:
            response = requests.get(url)

            # If the response status code is 200, the server is up and running
            if response.status_code == 200:
                print("runpod-worker-comfy - API is reachable")
                return True
        except requests.RequestException:
            # If an exception occurs, the server may not be ready
            pass

        # Wait for the specified delay before retrying
        time.sleep(delay / 1000)

    print(f"runpod-worker-comfy - Failed to connect to server at {url} after {retries} attempts.")
    return False


def upload_images(images: List[ComfyImageInput]):
    """
    Upload a list of base64 encoded images to the ComfyUI server using the /upload/image endpoint.

    Args:
        images (list): A list of dictionaries, each containing the 'name' of the image and the 'image' as a base64 encoded string.
        server_address (str): The address of the ComfyUI server.

    Returns:
        list: A list of responses from the server for each image upload.
    """
    if not images:
        return {"status": "success", "message": "No images to upload", "details": []}

    responses = []
    upload_errors = []

    print("runpod-worker-comfy - image(s) upload")

    for image in images:
        name = image.name
        image_data = image.image
        blob = base64.b64decode(image_data)

        # Prepare the form data
        files = {
            "image": (name, BytesIO(blob), "image/png"),
            "overwrite": (None, "true"),
        }

        # POST request to upload the image
        response = requests.post(f"http://{COMFY_HOST}/upload/image", files=files)
        if response.status_code != 200:
            upload_errors.append(f"Error uploading {name}: {response.text}")
        else:
            responses.append(f"Successfully uploaded {name}")

    if upload_errors:
        print("runpod-worker-comfy - image(s) upload with errors")
        return {
            "status": "error",
            "message": "Some images failed to upload",
            "details": upload_errors,
        }

    print("runpod-worker-comfy - image(s) upload complete")
    return {
        "status": "success",
        "message": "All images uploaded successfully",
        "details": responses,
    }


def upload_files_from_url(file_urls: List[ComfyFileUrlInput]):
    """
    Upload a list of file url that the handler would retrieve and post to Comfy UI server.

    Args:
        file_urls (list): A list of dictionaries, each containing the 'name' of the file and the 'url' string.

    Returns:
        list: A list of responses from the server for each file upload.
    """

    if not file_urls:
        return {"status": "success", "message": "No files to upload", "details": []}
    responses = []
    upload_errors = []

    for file_url in file_urls:
        name = file_url.name
        url = file_url.url
        print(f"runpod-worker-comfy - downloading {name} from {url}")
        try:
            session = requests.Session()

            encoder = MultipartEncoder(
                fields={
                    "image": (
                        name,
                        FileFromURLWrapper(url, session=session),
                        "application/octet-stream",
                    ),
                    "overwrite": "true",
                }
            )
            response = requests.post(
                f"http://{COMFY_HOST}/upload/image",
                data=encoder,
                headers={"Content-Type": encoder.content_type},
            )
            if response.status_code != 200:
                print(f"runpod-worker-comfy - Error uploading {name}: [{response.status_code}] {response.text}")
                upload_errors.append(f"Error uploading {name}: [{response.status_code}] {response.text}")
            else:
                responses.append(f"Successfully uploaded {name}")

        except requests.RequestException as e:
            print(f"runpod-worker-comfy - Error downloading {name}: {str(e)}")
            upload_errors.append(f"Error downloading {name}: {str(e)}")
            continue

    if upload_errors:
        print("runpod-worker-comfy - file(s) upload with errors")
        return {
            "status": "error",
            "message": "Some files failed to upload",
            "details": upload_errors,
        }
    print("runpod-worker-comfy - file(s) upload complete")
    return {
        "status": "success",
        "message": "All files uploaded successfully",
        "details": responses,
    }


def queue_workflow(workflow):
    """
    Queue a workflow to be processed by ComfyUI

    Args:
        workflow (dict): A dictionary containing the workflow to be processed

    Returns:
        dict: The JSON response from ComfyUI after processing the workflow
    """

    # The top level element "prompt" is required by ComfyUI
    data = json.dumps({"prompt": workflow}).encode("utf-8")

    req = urllib.request.Request(f"http://{COMFY_HOST}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())


def get_history(prompt_id):
    """
    Retrieve the history of a given prompt using its ID

    Args:
        prompt_id (str): The ID of the prompt whose history is to be retrieved

    Returns:
        dict: The history of the prompt, containing all the processing steps and results
    """
    with urllib.request.urlopen(f"http://{COMFY_HOST}/history/{prompt_id}") as response:
        return json.loads(response.read())


def base64_encode(img_path):
    """
    Returns base64 encoded image.

    Args:
        img_path (str): The path to the image

    Returns:
        str: The base64 encoded image
    """
    with open(img_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return f"{encoded_string}"


def check_file_path_exist(paths: list[str]) -> tuple[bool, list[str]]:
    """
    Returns whether the given list of file paths exist.
    Args:
        paths (list[str]): list of file paths

    Returns:
        tuple:
            bool: True if all files exist, False otherwise
            list[str]: list of file paths that do exist
    """
    is_all_exist: bool = True
    path_exists = []
    for path in paths:
        if not os.path.exists(path):
            is_all_exist = False
        else:
            path_exists.append(path)

    return (is_all_exist, path_exists)


def is_an_output_file(output):
    """
    Determine whether the given output is an "output" file
    Args:
        file_dict (dict): dict of file data returned from comfy ui server
    Returns:
        bool: True if the file is an output file, False otherwise
    """

    if isinstance(output, dict):
        return "filename" in output and "type" in output and output["type"] == "output"

    return False


def upload_files_to_s3(
    job_id: str,
    file_list: list,
    bucket_name: str,
    endpoint_url: str,
    access_key: str,
    secret_key: str,
):
    """
    Uploads files to s3 bucket storage.
    """
    config = Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"})
    endpoint_url = endpoint_url.rstrip("/")
    client_session = session.Session()
    client = client_session.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config,
    )

    bucket_urls = []

    for _file in file_list:
        file_name = _file.split("/")[-1]
        object_key = f"{job_id}/{file_name}"
        try:
            _ = client.upload_file(_file, bucket_name, object_key)
            bucket_urls.append(f"{endpoint_url}/{bucket_name}/{object_key}")
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise e

    return bucket_urls


def process_output_images(outputs, job_id, job_output_def: ComfyOutput | None = None):
    """
    This function takes the "outputs" from image generation and the job ID,
    then determines the correct way to return the image, either as a direct URL
    to an AWS S3 bucket or as a base64 encoded string, depending on the
    environment configuration.

    Args:
        outputs (dict): A dictionary containing the outputs from image generation,
                        typically includes node IDs and their respective output data.
        job_id (str): The unique identifier for the job.

    Returns:
        dict: A dictionary with the status ('success' or 'error') and the message,
              which is either the URL to the image in the AWS S3 bucket or a base64
              encoded string of the image. In case of error, the message details the issue.

    The function works as follows:
    - It first determines the output path for the images from an environment variable,
      defaulting to "/comfyui/output" if not set.
    - It then iterates through the outputs to find the filenames of the generated images.
    - After confirming the existence of the image in the output folder, it checks if the
      AWS S3 bucket is configured via the BUCKET_ENDPOINT_URL environment variable.
    - If AWS S3 is configured, it uploads the image to the bucket and returns the URL.
    - If AWS S3 is not configured, it encodes the image in base64 and returns the string.
    - If the image file does not exist in the output folder, it returns an error status
      with a message indicating the missing image file.
    """

    # The path where ComfyUI stores the generated images
    COMFY_OUTPUT_PATH = os.environ.get("COMFY_OUTPUT_PATH", "/comfyui/output")

    output_files = []

    for node_id, node_output in outputs.items():
        print(f"runpod-worker-comfy - node_id: {node_id} - node_output: {node_output}")

        for _, output in node_output.items():
            # check if any file output with type = "output"
            if isinstance(output, list):
                output_files.extend([output_item for output_item in output if is_an_output_file(output_item)])
            elif isinstance(output, dict):
                if is_an_output_file(output):
                    output_files.append(output)

    # list of output file path
    output_paths = [os.path.join(COMFY_OUTPUT_PATH, output["subfolder"], output["filename"]) for output in output_files]

    # check if the output files contains a .txt supplementary file
    output_text_paths = []
    for items in output_paths:
        txt_path = ".".join(items.split(".")[:-1]) + ".txt"
        if os.path.exists(txt_path):
            output_text_paths.append(txt_path)

    output_paths.extend(output_text_paths)

    if len(output_paths) > 0:
        print("runpod-worker-comfy - image generation is done")
        for path in output_paths:
            print(f"runpod-worker-comfy - {path}")
    else:
        print("runpod-worker-comfy - no image generated")
        return {
            "status": "error",
            "message": "No image generated",
        }

    if job_output_def and job_output_def.type == "s3":
        all_exist, output_paths = check_file_path_exist(output_paths)
        if not all_exist:
            print("runpod-worker-comfy - some files do not exist in the output folder")

        job_key_prefix = job_output_def.key_prefix
        aws_access_key_id = os.environ.get(job_key_prefix + "AWS_ACCESS_KEY_ID", None)
        aws_secret_key = os.environ.get(job_key_prefix + "AWS_SECRET_ACCESS_KEY", None)

        if (aws_access_key_id is None) or (aws_secret_key is None):
            print(
                f"runpod-worker-comfy - AWS credentials are missing: {job_key_prefix + 'AWS_ACCESS_KEY_ID'}, {job_key_prefix + 'AWS_SECRET_ACCESS_KEY'}"
            )
            return {
                "status": "error",
                "message": "AWS credentials are missing",
            }

        try:
            s3_urls = upload_files_to_s3(
                job_id,
                output_paths,
                job_output_def.bucket,
                job_output_def.endpoint_url,
                aws_access_key_id,
                aws_secret_key,
            )

        except Exception as e:
            print(f"runpod-worker-comfy - Error uploading files to s3: {str(e)}")
            return {
                "status": "error",
                "message": f"Error uploading files to s3: {str(e)}",
            }

        print("runpod-worker-comfy - the files were generated and uploaded to AWS S3")
        return {
            "status": "success",
            "message": s3_urls,
        }
    else:
        # return the images as base64, or follow the environment conf of BUCKET_ENDPOINT_URL and upload to s3
        output_images = []
        for path in output_paths:
            if os.path.exists(path):
                if os.environ.get("BUCKET_ENDPOINT_URL", False):
                    # URL to image in AWS S3
                    image = rp_upload.upload_image(job_id, path)
                    print("runpod-worker-comfy - the image was generated and uploaded to AWS S3")
                else:
                    # base64 image
                    image = base64_encode(path)
                    print("runpod-worker-comfy - the image was generated and converted to base64")
                output_images.append(image)
            else:
                print("runpod-worker-comfy - the image does not exist in the output folder")
                return {
                    "status": "error",
                    "message": f"the image does not exist in the specified output folder: {path}",
                }
        return {
            "status": "success",
            "message": output_images,
        }


def handler(job):
    """
    The main function that handles a job of generating an image.

    This function validates the input, sends a prompt to ComfyUI for processing,
    polls ComfyUI for result, and retrieves generated images.

    Args:
        job (dict): A dictionary containing job details and input parameters.

    Returns:
        dict: A dictionary containing either an error message or a success status with generated images.
    """

    try:
        job = ComfyWorkerJob(id=job["id"], **job["input"])
    except ValidationError as e:
        return {"error": f"Error validating input: {str(e)}"}

    trigger_handler = None
    if job.trigger:
        try:
            trigger_handler = create_trigger_handler(job.trigger)
        except ValueError as e:
            return {"error": f"Error creating trigger handler: {str(e)}"}

    # Make sure that the ComfyUI API is available
    check_server(
        f"http://{COMFY_HOST}",
        COMFY_API_AVAILABLE_MAX_RETRIES,
        COMFY_API_AVAILABLE_INTERVAL_MS,
    )

    # Upload images if they exist
    upload_result = upload_images(job.images)

    if upload_result["status"] == "error":
        return upload_result

    # Upload files from URLS if they exist
    upload_file_result = upload_files_from_url(job.file_urls)

    if upload_file_result["status"] == "error":
        return upload_file_result

    # Queue the workflow
    try:
        queued_workflow = queue_workflow(job.workflow)
        prompt_id = queued_workflow["prompt_id"]
        node_errors = queued_workflow["node_errors"]

        if node_errors:
            print(f"runpod-worker-comfy - Error found when queuing workflow: {node_errors}")
            return {"error": f"Error found when queuing workflow: {node_errors}"}
        else:
            print(f"runpod-worker-comfy - queued workflow with ID {prompt_id}")

    except Exception as e:
        return {"error": f"Error queuing workflow: {str(e)}"}

    # Poll for completion
    print("runpod-worker-comfy - wait until image generation is complete")
    retries = 0
    try:
        while retries < COMFY_POLLING_MAX_RETRIES:
            history = get_history(prompt_id)

            # Return error if we have found error in any history status
            if prompt_id in history:
                if history[prompt_id].get("status") == "error":
                    return {"error": f"Error in generation: {history[prompt_id].get('output')}"}
                elif history[prompt_id].get("outputs"):
                    # Otherwise, exit the loop if we have found the history with outputs
                    break
            else:
                # Wait before trying again
                time.sleep(COMFY_POLLING_INTERVAL_MS / 1000)
                retries += 1
        else:
            return {"error": "Max retries reached while waiting for image generation"}
    except Exception as e:
        return {"error": f"Error waiting for image generation: {str(e)}"}

    # Get the generated image and return it as URL in an AWS bucket or as base64
    images_result = process_output_images(history[prompt_id].get("outputs"), job.id, job.output)

    result = {**images_result, "refresh_worker": REFRESH_WORKER}

    if trigger_handler:
        # format output
        images = images_result["message"]
        assert isinstance(images, list), "images output should be a list of URLs, or base64 encoded images"
        output = json.dumps(images)
        response = trigger_handler.handle(output)
        print(f"Trigger response: {response}")

    return result


# Start the handler only if this script is run directly
if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
