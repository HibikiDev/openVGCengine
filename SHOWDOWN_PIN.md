# Pokémon Showdown pin

The engine ports Pokémon Showdown's simulator at one commit, and the buddy's server is built from the same commit: use exactly
this one (a newer Showdown may differ in mechanics and in its format list).

- **Repo:** https://github.com/smogon/pokemon-showdown
- **Commit:** `3661ce40bf9001d185ce078b8920e12304204609`

```sh
git clone https://github.com/smogon/pokemon-showdown vendor/pokemon-showdown
git -C vendor/pokemon-showdown checkout 3661ce40bf9001d185ce078b8920e12304204609
(cd vendor/pokemon-showdown && npm ci --omit=dev && node build)
```
