# Third-Party Attributions

## Hermes Agent (provider profile data)

`harness/providers.py` adapts the declarative provider-profile DATA (provider
names, API-key environment variable names, base URLs, API modes, and aliases)
from the Hermes Agent project's `providers/` and `plugins/model-providers/`
profiles.

Only the declarative profile data and shape are borrowed. Hermes's transport and
agent core are NOT used -- pm-harness keeps its own thin drivers
(`pmharness/drivers/openai_compat.py`, `pmharness/drivers/anthropic.py`).

  Hermes Agent
  Copyright (c) Nous Research
  Licensed under the MIT License.
  https://github.com/NousResearch/hermes-agent

The MIT License permits use, copy, modification, and distribution provided the
copyright notice and permission notice are retained. This NOTICE preserves that
attribution.
