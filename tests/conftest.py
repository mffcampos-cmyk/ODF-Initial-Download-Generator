# Resolves ODF_PACK_DIR (or known fallback locations) and refuses empty/decoy
# pack directories instead of silently running against an empty pack.
from generator.packload import load_refdata

PACK = load_refdata().pack

# Disciplines the generator deliberately refuses to build, and why. Tests that
# sweep every discipline skip these rather than treating a designed refusal as
# a failure -- but the set is asserted exactly (see
# test_refused_disciplines_are_exactly_the_known_set), so a discipline that
# starts refusing for a new reason is caught rather than absorbed.
#
# Empty since 2026-09-23: GAR used to refuse (its team events carry no squad
# size), but it is entered by gender (GARMGEN/GARWGEN) like the real feed, so
# no team is built and no squad size is needed.
REFUSED_DISCIPLINES: set[str] = set()

try:
    import pytest
except ImportError:  # sandbox fallback: minirunner imports this module without pytest
    pytest = None

if pytest is not None:
    @pytest.fixture(scope="session")
    def pack():
        return PACK
