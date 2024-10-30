import os
from typing import Literal

from pydantic import Field

import supabase

from .job import JobTrigger, TriggerHandler


class SupabaseJobTrigger(JobTrigger):
    "Supabase job trigger"

    service: Literal["supabase"] = Field(description="The service string is always 'supabase'")
    key_prefix: str = Field(description="The prefix of api key used in this job", min_length=1)
    table: str = Field(description="The table or collection to be updated")
    id_field: str = Field(description="The id field name of the entry")
    output_field: str = Field(description="The output field name, usually to store the model output (e.g. url)")
    status_field: str | None = Field(description="The status field name")
    id: str = Field(description="The id value of the entry to be updated when the job completed successfuly")
    status: str | None = Field(description="The status value to be updated when the job completed successfuly")


class SupabaseTriggerHandler(TriggerHandler):
    "Supabase trigger handler"

    def __init__(self, trigger: SupabaseJobTrigger):
        self.trigger = trigger

    def validate(self):
        "validate if the necessary env settings are set"

        if f"{self.trigger.key_prefix}SUPABASE_URL" not in os.environ:
            raise ValueError(f"{self.trigger.key_prefix}SUPABASE_URL not set in environment")
        if f"{self.trigger.key_prefix}SUPABASE_KEY" not in os.environ:
            raise ValueError(f"{self.trigger.key_prefix}SUPABASE_KEY not set in environment")

    def handle(self, output: str):
        "handle db update according to the job trigger"
        url = os.environ[f"{self.trigger.key_prefix}SUPABASE_URL"]
        key = os.environ[f"{self.trigger.key_prefix}SUPABASE_KEY"]
        client = supabase.create_client(url, key)

        data = {self.trigger.output_field: output}

        if self.trigger.status_field and self.trigger.status:
            data[self.trigger.status_field] = self.trigger.status

        print(f"Updating supabase: {data}")
        try:
            response = (
                client.table(self.trigger.table).update(data).eq(self.trigger.id_field, self.trigger.id).execute()
            )
        except Exception as e:
            print(f"Failed to update Supabase: {e}")
            raise e

        return response.model_dump_json()
