"""Tests never call the LLM gateway: they must pass offline and give the same answer every run."""
import os

os.environ["PRIOR_LLM"] = "off"
