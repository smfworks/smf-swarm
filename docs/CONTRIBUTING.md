# Contributing to SMF Swarm

Thank you for your interest! This project is the prediction engine behind
[SMF Works](https://smfworks.com).

## How to Contribute

1. **Open an issue first** describing the bug or feature. Wait for a maintainer
   to confirm before starting work.
2. **Fork the repo** and create a feature branch.
3. **Write tests** for new code.
4. **Run tests**: `pytest tests/`
5. **Submit a PR** with a clear description and linked issue.

## Code Style

- **Black** formatting: `black src/ tests/`
- Ruff for linting: `ruff check src/ tests/`
- Type hints on public APIs.

## Areas We Need Help

- **Resolution bots**: scrapers for sports, medical, and legal domains
- **LLM adapters**: Anthropic native, Google, Mistral AI
- **Community benchmarks**: run predictions, track outcomes, feed Brier scores

## Contact

- Email: michael@smfworks.com
- X: [@michaelgannotti](https://x.com/michaelgannotti)
- Issues: [github.com/smfworks/smf-swarm/issues](https://github.com/smfworks/smf-swarm/issues)

## License

All contributions are MIT licensed.
