from gt.analytics.bytecode import selectors_from_bytecode, selectors_from_source, similarity
from gt.simulator import simulate


def test_selector_from_source():
    assert selectors_from_source("function transfer(address to, uint256 amount) external") == {"a9059cbb"}


def test_source_canonicalizes_types_and_keywords():
    src = """
    function transfer(address payable to, uint amount) public returns (bool) {}
    function balanceOf(address owner) external view returns (uint256) {}
    // function notReal(uint256 x) commented out is still text; fine to include
    """
    sels = selectors_from_source(src)
    assert "a9059cbb" in sels            # uint → uint256, 'payable' dropped
    assert "70a08231" in sels            # balanceOf(address)


def test_selector_from_bytecode():
    assert selectors_from_bytecode("0x63a9059cbb14") == {"a9059cbb"}


def test_bytecode_skips_push_data_and_truncation():
    # PUSH32 whose data contains 0x63… must not be read as an opcode; trailing PUSH4 cut short is ignored
    code = "0x7f" + "63deadbeef" + "00" * 27 + "63a9059cbb" + "63aabb"
    assert selectors_from_bytecode(code) == {"a9059cbb"}
    assert selectors_from_bytecode("0x") == set() and selectors_from_bytecode("0xzz") == set()


def test_similarity():
    assert similarity({"a", "b"}, {"b", "c"}) == 1 / 3
    assert similarity(set(), {"a"}) == 0.0


def test_github_source_matches_deployed_exploit():
    s = simulate(seed=1)
    src = next(p.text for p in s.posts if p.source == "github")
    code = next(iter(s.bytecodes.values()))
    assert similarity(selectors_from_source(src), selectors_from_bytecode(code)) >= 0.6
