"""pm-harness: research rig for evaluating which LLMs can drive Puppetmaster
as a native harness layer (the PM-native driver-loop thesis).

Internal-first. Measures a *driver* model's ability to emit valid structured
orchestration intents and make correct decisions, with execution grounded on
Puppetmaster's free local adapter for deterministic, near-zero-cost evals.
"""

__version__ = "0.1.0"
