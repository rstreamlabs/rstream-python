# Django webhook receiver

Verify rstream signatures against the original body. Use an activated
virtual environment and run the commands from this directory.

```sh
python -m pip install -e "../../[examples]"
export RSTREAM_WEBHOOK_SECRET=whsec_local_example
python main.py
```

On Windows PowerShell set
`$env:RSTREAM_WEBHOOK_SECRET = 'whsec_local_example'` before running the
last command. The receiver listens on `127.0.0.1:8000`. The
[local delivery walkthrough](../../docs/003-webhooks.md#try-a-local-delivery)
checks the 200 and 400 responses with a signed fixture.
