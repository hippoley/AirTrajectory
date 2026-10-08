# Veklom EEE-Core coverage mapping (review artifact)

This artifact turns the question in
`reprewindai-dev/veklom-FRONTEND#146` into two concrete cases using only
EEE-Core's existing semantics.

EEE-Core already says:

- every execution attempt, including a denial, MUST produce one terminal Envelope;
- denied executions are first-class evidence;
- valid envelopes are independently verifiable;
- omission attacks are security-relevant;
- hash chains and settlement cross-checks can expose some omissions.

The remaining boundary is narrower:

> What object tells a verifier which execution attempts were required to exist
> before envelopes were emitted?

The machine-readable review cases live at:

`interop/veklom/eee-coverage-mapping-v0.1.json`

They freeze two distinctions:

```text
expected A,B + valid envelope A only
=> MISSING(B)

expected A,B + valid A + valid denied B
=> COMPLETE coverage
```

The second row matters because EEE already requires denials to produce
envelopes. A denied execution is therefore not an omission.

This mapping deliberately does not invent the authoritative expected-execution
object. If CAPPO, an authority artifact, a workflow plan, or another Veklom
object already provides that commitment, issue #146 can close by pointing the
coverage check at that existing object.
