# WB SERP Railway Implementation Plan

**Goal:** Deploy a standalone resumable WB SERP collector compatible with the current YAML and CSV contracts.

**Architecture:** Small Python modules separate YAML loading, curl-template parsing, response normalization, checkpoint storage, and orchestration. Railway runs the CLI from Docker and persists state under `/data`.

**Tech Stack:** Python 3.13, PyYAML, standard library HTTP/curl subprocess, pytest, Railway Docker/Cron.

## Tasks

- [ ] Add failing tests for nested YAML query loading and de-duplication.
- [ ] Implement the YAML loader.
- [ ] Add failing tests for product normalization and price conversion.
- [ ] Implement compact current-compatible SERP rows.
- [ ] Add failing tests for checkpoint resume and merged outputs.
- [ ] Implement checkpoints, error recording, and orchestration.
- [ ] Add Dockerfile, Railway config, sample variables, and operating README.
- [ ] Run all tests and a no-network dry run.
- [ ] Commit and push to `BahramBobojonov/wb_serp`.
