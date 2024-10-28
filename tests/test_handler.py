from src.rp_handler import validate_input, handler, ComfyWorkerJob


def test_validation(job):
    result = validate_input(job)
    assert result is not None


def test_new_pydantic_input_validation(job):
    job_input = job['input']
    job = ComfyWorkerJob(**job_input)
    assert job.workflow == job_input['workflow']
    assert job.images
    assert job.file_urls
    assert job.output
    assert job.trigger


def test_handler(job):

    try:
        res = handler(job)
    except Exception as e:
        print(e)
        res = None

    assert res is not None
