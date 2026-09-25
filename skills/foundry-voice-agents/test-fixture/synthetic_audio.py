"""Generate only the reviewed synthetic test utterances using existing Speech.

No microphone or arbitrary input. Generated audio is private run-owned data.
"""

from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

import requests
from azure.identity import AzureCliCredential

UTTERANCES = {
    "hours": "What are the fictional demo opening hours?",
    "long": (
        "Explain the fictional demo opening hours slowly using exactly ten sentences "
        "after calling the opening hours tool."
    ),
    "interrupt": "Stop. Just tell me the hours.",
}


def synthesize(
    directory: Path, endpoint: str, account_id: str, credential: AzureCliCredential,
    *, names: tuple[str, ...] = tuple(UTTERANCES),
) -> dict[str, Path]:
    url = urlsplit(endpoint)
    if (url.scheme != "https" or not url.hostname
            or not url.hostname.endswith(".cognitiveservices.azure.com")
            or url.query or url.fragment or url.username or url.password):
        raise ValueError("Expected the approved existing Speech account endpoint")
    if "/providers/Microsoft.CognitiveServices/accounts/" not in account_id:
        raise ValueError("Expected the approved existing account ARM ID")
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token
    paths = {}
    if not names or any(name not in UTTERANCES for name in names):
        raise ValueError("Only fixed reviewed synthetic utterances are supported")
    for name in names:
        text = UTTERANCES[name]
        body = (
            '<speak version="1.0" xml:lang="en-US">'
            f'<voice name="en-US-JennyNeural">{escape(text)}</voice></speak>'
        )
        response = requests.post(
            endpoint.rstrip("/") + "/tts/cognitiveservices/v1",
            headers={
                "Authorization": f"Bearer aad#{account_id}#{token}",
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                "User-Agent": "awesome-gbb-voice-acceptance",
            },
            data=body.encode("utf-8"), timeout=(10, 45), allow_redirects=False,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Synthetic Speech request failed HTTP {response.status_code}")
        path = directory / f"{name}.wav"
        with path.open("xb") as output:
            output.write(response.content)
        paths[name] = path
    return paths
