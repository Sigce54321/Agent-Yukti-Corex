"""Select Java sandbox commands without compiling or executing source code."""

from pathlib import Path
import re

from .base import BaseLanguageAdapter


_NON_CODE = re.compile(
    r'//[^\n]*|/\*.*?\*/|""".*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
    re.DOTALL,
)
_MAIN = re.compile(
    r"\bpublic\s+static\s+void\s+main\s*\(\s*(?:java\.lang\.)?String\s*"
    r"(?:\[\s*\]|\.\.\.)\s+\w+\s*\)\s*(?:throws\s+[\w.,\s]+)?\{"
)
_JAVA_LANG = set(
    "String StringBuilder StringBuffer System Object Class Math StrictMath "
    "Integer Long Double Float Short Byte Boolean Character Number Enum Record "
    "Exception RuntimeException IllegalArgumentException IllegalStateException "
    "NullPointerException UnsupportedOperationException ArithmeticException "
    "IndexOutOfBoundsException AssertionError Error Throwable Thread Runnable "
    "AutoCloseable Comparable Iterable Override SuppressWarnings Deprecated".split()
)


def _workspace(workspace_path: str) -> Path | None:
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        return None
    root = Path(workspace_path)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[1] / root
    root = root.resolve(strict=True)
    return root if root.is_dir() else None


def _safe_file(path: Path, root: Path) -> bool:
    return (
        not path.is_symlink() and path.is_file()
        and path.resolve(strict=True).is_relative_to(root)
    )


def _standalone(path: Path, root: Path) -> bool:
    """Recognize a conservative subset of single-class, JDK-only programs."""
    if not _safe_file(path, root):
        return False
    code = _NON_CODE.sub(" ", path.read_text(encoding="utf-8-sig"))
    if re.search(r"\bpackage\s", code):
        return False
    imports = re.findall(r"\bimport\s+([^;]+);", code)
    # Reject wildcard/static imports and dependencies requiring a classpath.
    if any(not re.fullmatch(r"java\.(?:\w+\.)+[A-Z]\w*", item.strip()) for item in imports):
        return False
    code = re.sub(r"\bimport\s+[^;]+;", " ", code)
    classes = re.findall(r"\b(?:class|interface|enum|record)\s+(\w+)", code)
    if classes != [path.stem]:
        return False
    main = _MAIN.search(code)
    if main is None:
        return False
    prefix = code[:main.start()]
    if prefix.count("{") - prefix.count("}") != 1:
        return False
    allowed_types = _JAVA_LANG | {path.stem} | {item.strip().rsplit(".", 1)[-1] for item in imports}
    # Unknown capitalized identifiers may be unimported project dependencies.
    identifiers = re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", code)
    return all(name in allowed_types or name.isupper() for name in identifiers)


class JavaAdapter(BaseLanguageAdapter):
    """Provide offline Maven tests and conservative Java source-file commands."""

    def get_test_command(self, workspace_path: str) -> list[str]:
        """Prefer Maven, then the HTML contract test and standalone test files."""
        try:
            root = _workspace(workspace_path)
            if root is None:
                return []
            if _safe_file(root / "pom.xml", root):
                return ["mvn", "--offline", "--batch-mode", "test"]
            preferred = root / "src/test/java/HtmlContractTest.java"
            candidates = [preferred]
            for directory in (root, root / "src/test/java", root / "tests"):
                if directory.is_dir() and directory.resolve(strict=True).is_relative_to(root):
                    candidates.extend(sorted(directory.glob("*Test.java")))
                    candidates.extend(sorted(directory.glob("Test*.java")))
            for candidate in candidates:
                if _standalone(candidate, root):
                    return ["java", candidate.relative_to(root).as_posix()]
        except (OSError, RuntimeError, ValueError, UnicodeError):
            return []
        return []

    def get_run_command(self, workspace_path: str) -> list[str]:
        """Select a conventional or unambiguous standalone application source."""
        try:
            root = _workspace(workspace_path)
            if root is None:
                return []
            candidates = []
            for directory in (root, root / "src/main/java"):
                if directory.is_dir() and directory.resolve(strict=True).is_relative_to(root):
                    candidates.extend(sorted(directory.glob("*.java")))
            supported = [
                path for path in candidates
                if not (path.stem.startswith("Test") or path.stem.endswith("Test"))
                and _standalone(path, root)
            ]
            for name in ("Main.java", "App.java"):
                matches = [path for path in supported if path.name == name]
                if len(matches) == 1:
                    return ["java", matches[0].relative_to(root).as_posix()]
            if len(supported) == 1:
                return ["java", supported[0].relative_to(root).as_posix()]
        except (OSError, RuntimeError, ValueError, UnicodeError):
            return []
        return []

    def get_language_image(self) -> str:
        """Return the image tag expected by the sandbox runner."""
        return "yuktic-orex-java:latest"
