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
# GAR: its three team events carry no squad size in the event code, and the
# Common Codes tables have no squad-size column. Rather than default to a
# plausible-looking number, eventstructure.squad_size raises UnknownSquadSize.
REFUSED_DISCIPLINES = {"GAR"}

try:
    import pytest
except ImportError:  # sandbox fallback: minirunner imports this module without pytest
    pytest = None

if pytest is not None:
    @pytest.fixture(scope="session")
    def pack():
        return PACK
