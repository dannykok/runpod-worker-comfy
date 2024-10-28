from pydantic import ValidationError
from .supabase import SupabaseTriggerHandler, SupabaseJobTrigger
from .job import JobTrigger


def create_trigger_handler(job_trigger: JobTrigger):
    "Validate if the trigger is properly setup"
    trigger_handler = None

    if isinstance(job_trigger, SupabaseJobTrigger):
        trigger_handler = SupabaseTriggerHandler(job_trigger)
        trigger_handler.validate()
    else:
        raise ValueError("Unsupported service")

    return trigger_handler
