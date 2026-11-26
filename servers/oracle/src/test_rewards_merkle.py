"""Tests for OpenZeppelin StandardMerkleTree parity in Python."""

import pytest
from eth_utils import keccak
from web3 import Web3

from oracle.src.rewards.epoch_json import build_epoch_json, serialize_epoch_json, verify_epoch_json_merkle
from oracle.src.rewards.merkle import StandardMerkleTree, ZERO_ROOT, hash_leaf, verify_proof
from oracle.src.rewards.rpc_client import abi_encode


def _addr(i: int) -> str:
    return "0x" + f"{i + 1:040x}"


def test_empty_tree_has_zero_root():
    ep = build_epoch_json(
        epoch=1,
        snapshot_block=100,
        holders=[],
        balances=[],
        registered_contracts=[],
        expected_total=0,
    )
    assert ep.merkle_root == ZERO_ROOT
    assert ep.holders == []
    verify_epoch_json_merkle(ep, ZERO_ROOT)


def test_single_leaf_matches_solidity_double_hash():
    addr = "0x1111111111111111111111111111111111111111"
    amount = 100 * 10**18
    expected_leaf = keccak(
        keccak(abi_encode(["address", "uint256"], [Web3.toChecksumAddress(addr), amount]))
    )
    assert hash_leaf(addr, amount) == expected_leaf

    tree = StandardMerkleTree([(addr, amount)])
    assert tree.root == "0x" + expected_leaf.hex()
    assert tree.get_proof(0) == []
    assert verify_proof(expected_leaf, [], tree.root)


@pytest.mark.parametrize("count", [1, 2, 3, 50, 500])
def test_standard_merkle_tree_proofs_verify_for_all_sizes(count):
    entries = [(_addr(i), (i + 1) * 10**18) for i in range(count)]
    tree = StandardMerkleTree(entries)

    assert tree.root.startswith("0x")
    assert len(tree.root) == 66

    for idx, (addr, amount) in enumerate(entries):
        proof = tree.get_proof(idx)
        leaf = hash_leaf(addr, amount)
        assert verify_proof(leaf, proof, tree.root)
        # Tampering with amount must fail verification
        bad_leaf = hash_leaf(addr, amount + 1)
        assert not verify_proof(bad_leaf, proof, tree.root)


def test_standard_merkle_tree_is_order_independent_for_root():
    entries = [(_addr(i), (i + 7) * 123456789) for i in range(15)]
    tree_a = StandardMerkleTree(entries)
    tree_b = StandardMerkleTree(list(reversed(entries)))
    assert tree_a.root == tree_b.root


def test_two_leaf_golden_pair_ordering():
    a = ("0x0000000000000000000000000000000000000001", 100)
    b = ("0x0000000000000000000000000000000000000002", 200)
    la = hash_leaf(*a)
    lb = hash_leaf(*b)
    expected_root = "0x" + (keccak(la + lb) if la <= lb else keccak(lb + la)).hex()

    tree = StandardMerkleTree([a, b])
    assert tree.root == expected_root
    assert tree.get_proof(0) == ["0x" + lb.hex()]
    assert tree.get_proof(1) == ["0x" + la.hex()]


def test_build_epoch_json_rejects_duplicate_or_total_mismatch():
    with pytest.raises(ValueError, match="Duplicate holder"):
        build_epoch_json(
            epoch=1,
            snapshot_block=10,
            holders=[(_addr(0), 10), (_addr(0).upper().replace("0X", "0x"), 20)],
            balances=[],
            registered_contracts=[],
            expected_total=30,
        )

    with pytest.raises(ValueError, match="does not match"):
        build_epoch_json(
            epoch=1,
            snapshot_block=10,
            holders=[(_addr(0), 10)],
            balances=[],
            registered_contracts=[],
            expected_total=99,
        )


# Golden vectors generated directly with `@openzeppelin/merkle-tree`
# (`StandardMerkleTree.of(entries, ["address", "uint256"])`) in `rewards-program`.
OZ_GOLDEN_VECTORS = [
    (
        1,
        "0x6081e60a560cf21a6ea538bd62fec907bc40d5711c5e8c7e8fbe6dc134b72608",
        {0: []},
    ),
    (
        2,
        "0x03c0b05ec3ddabd05619c2171b32592eb04182e79274e6c7e0cc58ef91437dd3",
        {
            0: ["0x09ef46ce7299321a1324f25b2d659db10365f7155d3b3af2012d212aa90c6792"],
            1: ["0x6081e60a560cf21a6ea538bd62fec907bc40d5711c5e8c7e8fbe6dc134b72608"],
        },
    ),
    (
        3,
        "0x1f15d1edd8ec9df5444bcc9f906af766538008cc6b818dfba1edf8617ce6d961",
        {
            0: [
                "0x09ef46ce7299321a1324f25b2d659db10365f7155d3b3af2012d212aa90c6792",
                "0xb087824e64c5eb01d09207d4a703256c1b0d5c2145276f486085e3e4d39df4f1",
            ],
            1: [
                "0x6081e60a560cf21a6ea538bd62fec907bc40d5711c5e8c7e8fbe6dc134b72608",
                "0xb087824e64c5eb01d09207d4a703256c1b0d5c2145276f486085e3e4d39df4f1",
            ],
            2: ["0x03c0b05ec3ddabd05619c2171b32592eb04182e79274e6c7e0cc58ef91437dd3"],
        },
    ),
    (
        50,
        "0xec662b0db183acc694b5585792ca2aaea225e507bacac6e60ca449bb172c6a97",
        {
            0: [
                "0x60ff8ec4a72338dd85179fb9703448b56178e2e82855f71ecea0dcaf49ed862a",
                "0x00bcd408c6bb8e58cf51149543417c684e3c7ece64b614017bdf3b829a8b18a1",
                "0x9cff4bc82024281cb7812b20b25a55841cd9eb15ac3a275b0270c0181a0949a5",
                "0xe639da083c73f89de07114c89139374f0f33beed7f42213271c8ee0ba8d3f65c",
                "0x32337c66f126ade14ecc3f7ec45de187396d5a4bf37dc531a48fb499ed7b2041",
                "0xb8c27280783a5ef77fd7eca488c0a383046fd5501278f7a5b509fb69462bc9a7",
            ],
            25: [
                "0x456537acd9e0986faa2b7e73e1a9dc47e9b25a148f768671c1b758002dd48616",
                "0x289465b90b5645586f65fd8f64658ef14760d70a9acbaf469da4fbc3e3daddaf",
                "0xadad69013cbf8de0e20d151c564bcf6b269d90dd700c2aa4c62e824930b4686b",
                "0xbaccdef9c09a1bf8312cbb25a6c015b4f9b290114c84af6f99740298ff88eb14",
                "0x356d7b1211f1a7d4b520c75462407a8c7e611a0f25ae3df9e1fe16dd0f155e75",
                "0xb8c27280783a5ef77fd7eca488c0a383046fd5501278f7a5b509fb69462bc9a7",
            ],
            49: [
                "0x52fde9620166090d16073b89092702f9d9ded0e2350a680cad51cd3cd64d6075",
                "0x85f491ed13828f6e6c76db0fdbfdb2e42baa12a2ec1fb0e123503997f801acd5",
                "0xadad69013cbf8de0e20d151c564bcf6b269d90dd700c2aa4c62e824930b4686b",
                "0xbaccdef9c09a1bf8312cbb25a6c015b4f9b290114c84af6f99740298ff88eb14",
                "0x356d7b1211f1a7d4b520c75462407a8c7e611a0f25ae3df9e1fe16dd0f155e75",
                "0xb8c27280783a5ef77fd7eca488c0a383046fd5501278f7a5b509fb69462bc9a7",
            ],
        },
    ),
    (
        500,
        "0xac8cf4b705278aba13c40424a0eb0ffb0a963b934306b313605ff7ed707c7ff4",
        {
            0: [
                "0x5fff3e94bb543d3b3927eb071931301d15b2709c8bbba4688c628926816bac55",
                "0x7e9d691e8a215608c0feaa6a540998dfdcd035475a2bf7026c5fc399281db3be",
                "0x26296c95c1e6920ec6092718a868ee76b1d6414b679d7d60a29c28a766483085",
                "0xe4b3194862bf286f2f5866413a532aede9df89f648c5a32f4ea20e5476a32a68",
                "0x94386abe75e9df607574428d662a52e2dc1ddfff350443284540c0af561e203e",
                "0x1ad3ab657e6656341562cc281737b65e9dd453cf7d56802890cbbba1cf9f8f66",
                "0xdcac6bce6d444a87c53379d4a36440cd5e100ba4d4b6fcd2cab1283f2d4880e9",
                "0x5e9d1daed9328081b42d1550d111beeaa4ce0179cba912eb4921cb2eb044df80",
                "0x9209689fa8a24512a01c43d483b8f02ed30935d612cc14f0ab2b956ea6fb6108",
            ],
            250: [
                "0xbde2a8fa5e798a3a961c7f60c3e10c412030e061226f8cdcced4d6dd7d5125bf",
                "0x462deb5dbc59c41a1a64b34e5004ea7eaf7f3171041ee739bef5b264c5d0adf5",
                "0xbd95416f2907ffe16cd36e69c1ec3f5bec0fe50e49f17650d18828b706feeaba",
                "0x600efe01525c76c79df3ca471156fedfaa2937483a5eeba9539780ee46f7f291",
                "0xa50070aab0698ef522b86924cd11f14f58299ef29af6e4b6c295f0f675fb8bb5",
                "0xb5170ece6a3d9b3a0bcc1fee907a9666962625b309443e469661bdc9e2755de5",
                "0x78e22fb00ec3bd25e67344c1fda131a4b751f2be1981f0be83cbabb5927354bd",
                "0x6660a210ec8544aca9abbf45ed1844dc9c9d8c294edd5ffd6d242988ccc2769b",
                "0x16d71774e42ce8afa29aba1e49317c8f980665fbe752814770ed7ef8086c8395",
            ],
            499: [
                "0xe94cd4097d05cf17d26b1c6bb12ab4313a3c724cae300b12482a9fe402abce98",
                "0x1070a772b01ba65420f2a572b9c46f566a1c47814ac665b692137d0b180eebc1",
                "0x244623eaf17d64fae2cfaa3bd003dccf33e1b2ce8b72b5ec38068af33e71f9eb",
                "0x12be5f44218476406410d58dce862114077ea7e0cc91219956654961ce151638",
                "0x83975a6c9b2c13cf8e8523a6014051122314879a20b3785c7fc1da6631ee384b",
                "0x0ac30ba22db9b6ba1f1de08d7336dd8aab015b2d933decd4c3ce64f1ee2cd080",
                "0x09ca733568c6021bf4dce7877c2c38f98bca582534ae0cf2ba4549ad02814d4c",
                "0x6660a210ec8544aca9abbf45ed1844dc9c9d8c294edd5ffd6d242988ccc2769b",
                "0x16d71774e42ce8afa29aba1e49317c8f980665fbe752814770ed7ef8086c8395",
            ],
        },
    ),
]


@pytest.mark.parametrize("count,expected_root,expected_proofs", OZ_GOLDEN_VECTORS)
def test_standard_merkle_tree_matches_openzeppelin_golden_vectors(
    count, expected_root, expected_proofs
):
    entries = [(_addr(i), (i + 1) * 10**18) for i in range(count)]
    tree = StandardMerkleTree(entries)
    assert tree.root == expected_root
    for idx, expected_proof in expected_proofs.items():
        assert tree.get_proof(idx) == expected_proof
