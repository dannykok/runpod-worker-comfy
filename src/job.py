from abc import ABC, abstractmethod
from typing import Dict, Literal

from pydantic import BaseModel, Field

ComfyWorkflow = Dict


class ComfyImageInput(BaseModel):
    name: str = Field(description="The name of the image")
    image: str = Field(description="The base64 encoded image")


class ComfyFileUrlInput(BaseModel):
    name: str = Field(description="The name of the file")
    url: str = Field(description="The url of the file")


class ComfyOutput(BaseModel):
    type: Literal["s3", "url"] = Field(description="The output type")
    bucket: str = Field(description="The bucket to store the output")
    endpoint_url: str = Field(description="The endpoint url")
    key_prefix: str = Field(description="The prefix for the key")


class JobTrigger(BaseModel):
    "Define the trigger after the job has completed"

    service: str = Field(description="The service to trigger")
    multiple_result: str = Field(
        default=False,
        description="Declare the workflow should produce multiple results, hence list will be used as output type",
    )


class TriggerHandler(ABC):
    @abstractmethod
    def validate(self):
        pass

    @abstractmethod
    def handle(self, output: str):
        pass
