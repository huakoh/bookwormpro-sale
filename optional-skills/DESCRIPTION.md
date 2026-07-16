# Optional Skills

Official skills maintained by BookwormPRO Project that are **not activated by default**.

These skills ship with the bookwormpro repository but are not copied to
`~/.bookwormpro/skills/` during setup. They are discoverable via the Skills Hub:

```bash
bookworm skills browse               # browse all skills, official shown first
bookworm skills browse --source official  # browse only official optional skills
bookworm skills search <query>       # finds optional skills labeled "official"
bookworm skills install <identifier> # copies to ~/.bookwormpro/skills/ and activates
```

## Why optional?

Some skills are useful but not broadly needed by every user:

- **Niche integrations** — specific paid services, specialized tools
- **Experimental features** — promising but not yet proven
- **Heavyweight dependencies** — require significant setup (API keys, installs)

By keeping them optional, we keep the default skill set lean while still
providing curated, tested, official skills for users who want them.
