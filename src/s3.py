from boto3 import session
from botocore.config import Config


def upload_files_to_s3(job_id: str,
                       file_list: list,
                       bucket_name: str,
                       endpoint_url: str,
                       access_key: str,
                       secret_key: str,
                       ):
    '''
    Uploads files to s3 bucket storage.
    '''
    config = Config(
        signature_version='s3v4',
        retries={
            'max_attempts': 3,
            'mode': 'standard'
        }
    )

    client_session = session.Session()

    client = client_session.client(
        's3',
        endpoint_url=endpoint_url.rstrip('/'),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config)

    bucket_urls = []

    for _file in file_list:
        with open(_file, 'rb') as file_data:
            file_name = _file.split('/')[-1]
            object_key = f"{job_id}/{file_name}"
            try:
                res = client.upload_file(
                    _file, bucket_name, object_key)
                bucket_urls.append(f"{endpoint_url}/{object_key}")
            except Exception as e:
                print(f"Error uploading file: {e}")
                raise e

    return bucket_urls
