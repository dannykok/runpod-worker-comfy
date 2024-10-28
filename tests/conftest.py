import pytest


@pytest.fixture(scope="session")
def job():
    "return a sample workflow input"
    return {
        "input": {
            "workflow": {
                "3": {
                    "inputs": {
                        "seed": 234234,
                        "steps": 20,
                        "cfg": 8,
                    },
                    "class_type": "KSampler"
                },
            },
            "images": [{
                "name": "somegif.gif",
                "image": "somebase64imagestring"
            }],
            "file_urls": [{
                "name": "somefile.txt",
                "url": "http://someurl.com"
            }],
            "output": {
                "type": "s3",
                "bucket": "somebucket",
                "endpoint_url": "http://someurl.com",
                "key_prefix": "FOO"
            },
            "trigger": {
                "service": "supabase",
                "key_prefix": "FOO",
                "table": "jobs",
                "id_field": "id",
                "output_field": "output",
                "status_field": "status",
                "id": "someid",
                "status": "completed"
            }
        }
    }
