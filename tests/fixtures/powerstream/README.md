# PowerStream protocol fixtures

Step 0 created this fixture directory for captured/prototype payloads.

The old prototype repository was reviewed via GitHub's web view because direct
`git clone`/raw downloads from this environment are blocked by a 403 CONNECT
tunnel. The prototype currently does not expose standalone binary fixture files;
Step 1 therefore uses deterministic protocol vectors in
`tests/adapters/powerstream/test_protocol.py` until real BLE captures are added.
