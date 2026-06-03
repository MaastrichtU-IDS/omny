# Releasing omny

Walk-through for the three one-time steps that aren't part of the
repo's CI: GitHub repo rename, PyPI trusted-publisher setup, and the
first tag-and-release. Once these are done, future releases are
just `git tag v0.1.1 && git push --tags`.

## 1. Rename the GitHub repo

```bash
gh api -X PATCH /repos/MaastrichtU-IDS/pymos \
  --field name=omny
```

What this does:

- Repo URL becomes `https://github.com/MaastrichtU-IDS/omny`.
- GitHub auto-redirects old URLs (`/pymos/*` → `/omny/*`) indefinitely,
  including clone URLs (`git clone …/pymos.git` still works and just
  rewrites the remote on the next `git fetch`).
- Existing branches, PRs, issues, releases, and CI history carry over
  unchanged.
- Local checkouts: `git remote set-url origin git@github.com:MaastrichtU-IDS/omny.git`
  (optional; works without the change too).

**After the rename, update the local working dir if you want consistency:**

```bash
# The directory on disk still says /data/dumontier/pymos.
# Renaming it requires being outside the dir:
cd /data/dumontier
mv pymos omny
cd omny
git remote set-url origin git@github.com:MaastrichtU-IDS/omny.git
```

(Sibling worktree at `/data/dumontier/pymos-run` would need the same
treatment if you keep it.)

## 2. PyPI trusted-publisher setup (one-time)

Trusted publishing means **no API token to store anywhere** —
GitHub Actions presents an OIDC token to PyPI, which validates it
against the configured publisher and authorises the upload. Set up
**before** the first release tag because the first publish for a
brand-new project needs the publisher pre-registered.

Steps:

1. Log in to PyPI: <https://pypi.org/account/login/> (create an
   account if needed; you'll be the owner).
2. Go to **Account settings → Publishing → Add a new pending publisher**:
   <https://pypi.org/manage/account/publishing/>
3. Fill in:
   - **PyPI Project Name:** `omny`
   - **Owner:** `MaastrichtU-IDS`
   - **Repository name:** `omny`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
4. Save.

That's it. The project will be created on PyPI on first publish
(no upfront "register project" step needed with trusted publishing).

Optional: set the same up on TestPyPI (<https://test.pypi.org>) if
you want to do a dry-run publish first. Tag scheme: same as below,
but you'd point the workflow at `https://test.pypi.org/p/omny` instead.

## 3. Tag and release v0.1.0

The `publish.yml` workflow triggers on any tag matching `v*`. So:

```bash
# Make sure your working tree is on the master commit you want to ship
git checkout master
git pull origin master

# Tag and push
git tag -a v0.1.0 -m "First PyPI release as omny

See CHANGELOG.md for the full release notes."
git push origin v0.1.0
```

What happens next:

1. GitHub Actions kicks off `publish.yml`.
2. The `build` job runs `python -m build` and uploads the artifacts.
3. The `publish` job downloads them and posts to
   <https://upload.pypi.org/legacy/> using OIDC (no token).
4. Within ~1 minute, `pip install omny` works for anyone.

Verify:

```bash
# In a clean venv somewhere else
python -m venv /tmp/verify-omny
/tmp/verify-omny/bin/pip install omny
/tmp/verify-omny/bin/python -c "import omny; print(omny.__version__)"
# Expected: 0.1.0
```

Also visible at <https://pypi.org/project/omny/>.

## Subsequent releases

**Important: bump `pyproject.toml` *before* tagging.** If you tag
without bumping, the build produces a wheel with the previous
version number, PyPI rejects it as a duplicate, and the
publish workflow fails silently as far as PyPI is concerned.
Since 0.2.1, `publish.yml` has a guard that fails the workflow
loudly with a clear "tag vX.Y.Z does not match pyproject version"
error before the build step — but it's still better to do the bump
in the same commit as the CHANGELOG note.

```bash
# 1. Bump pyproject.toml AND CHANGELOG.md in one commit on master
sed -i 's/^version = .*/version = "0.2.2"/' pyproject.toml
# (add a new ## [0.2.2] — YYYY-MM-DD section at the top of CHANGELOG.md)
git commit -am "release: 0.2.2"
git push

# 2. Tag and push (tag the commit that contains the bump)
git tag -a v0.2.2 -m "release 0.2.2"
git push origin v0.2.2
```

The `publish.yml` workflow takes care of the rest. If the tag-vs-pyproject
versions don't match, the workflow fails at the "Verify tag matches
pyproject.toml version" step before doing any work.

## If something goes wrong

**Workflow fails with "no trusted publisher configured":**
The PyPI pending-publisher setup step (#2) wasn't done, or one of
the fields doesn't match exactly. Re-check the publisher config —
owner / repo / workflow / environment are all case-sensitive.

**Workflow fails with "package already exists at version 0.1.0":**
PyPI doesn't allow re-uploading an existing version. Bump to the
next version (`0.1.0.post1` or `0.1.1`), commit, re-tag, push.

**`pip install omny` returns the wrong package:**
Check <https://pypi.org/project/omny/> — if a different project
already owns the name, the trusted-publisher setup will have failed
at step #2. (Pre-rename, we verified `omny` was free on 2026-06-02;
if it's been claimed since, see the candidate list in PR #52's
discussion thread.)

**Tag pushed but no workflow run:**
Tag name must match `v*` exactly. `v0.1.0` works; `0.1.0` (no `v`)
or `release-0.1.0` don't.
