import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
LOCK = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))


class TestFrontendSecurityDependencies(unittest.TestCase):
    def test_direct_vite_floor_is_patched(self) -> None:
        self.assertEqual(PACKAGE["dependencies"]["vite"], "^8.2.4")
        self.assertEqual(LOCK["packages"][""]["dependencies"]["vite"], "^8.2.4")

    def test_vite_and_follow_redirects_are_patched(self) -> None:
        packages = LOCK["packages"]
        self.assertEqual(packages["node_modules/vite"]["version"], "8.2.4")
        self.assertEqual(
            packages["node_modules/vite"]["integrity"],
            "sha512-lfauXnrf2x0p+UoA+wXh0dgFWnUjCyG6Js95KBkgaCwUU9k0DAHI4W6Q0WCx+h+5g+Alce1y4Zi2QjjK0UvGBw==",
        )
        self.assertEqual(packages["node_modules/follow-redirects"]["version"], "1.16.1")
        self.assertEqual(
            packages["node_modules/follow-redirects"]["integrity"],
            "sha512-FNvFGzoMLWmE6Yj9spb/zjd7yiNCHiAW9/Tg9CXrQ8wuu32HtlJOwWO11OJafl5FfY3DxTdQ0vj42zU1kvv5jg==",
        )

    def test_vite_patch_dependency_chain_is_coherent(self) -> None:
        packages = LOCK["packages"]
        vite = packages["node_modules/vite"]
        self.assertEqual(vite["dependencies"]["rolldown"], "~1.2.4")
        self.assertEqual(vite["dependencies"]["postcss"], "^8.5.26")
        rolldown = packages["node_modules/rolldown"]
        self.assertEqual(rolldown["version"], "1.2.4")
        self.assertEqual(rolldown["dependencies"]["@oxc-project/types"], "=0.144.0")
        self.assertEqual(packages["node_modules/@oxc-project/types"]["version"], "0.144.0")

    def test_all_rolldown_native_bindings_follow_1_2_4(self) -> None:
        packages = LOCK["packages"]
        bindings = {
            path: data
            for path, data in packages.items()
            if path.startswith("node_modules/@rolldown/binding-")
        }
        self.assertEqual(len(bindings), 14)
        self.assertTrue(all(data["version"] == "1.2.4" for data in bindings.values()))
        expected = set(packages["node_modules/rolldown"]["optionalDependencies"])
        actual = {path.removeprefix("node_modules/") for path in bindings}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
