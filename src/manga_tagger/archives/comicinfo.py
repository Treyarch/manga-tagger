"""ComicInfo.xml model. Edits the parsed tree so unknown XML is kept."""

from collections.abc import Mapping

from lxml import etree

from manga_tagger.archives.errors import ArchiveError, UnreadableArchiveError

OWNED_ELEMENTS: tuple[str, ...] = (
    "Title",
    "Series",
    "Number",
    "Volume",
    "Publisher",
    "PageCount",
    "LanguageISO",
    "AgeRating",
    "Manga",
    "Genre",
    "Summary",
    "Web",
    "CommunityRating",
    "Notes",
    "Year",
    "Month",
    "Day",
    "Writer",
    "Penciller",
    "Inker",
    "CoverArtist",
)

BATCH_FIELDS: frozenset[str] = frozenset(
    {
        "Series",
        "Publisher",
        "LanguageISO",
        "Genre",
        "Writer",
        "Penciller",
        "Inker",
        "CoverArtist",
        "Manga",
    }
)


class ComicPage:
    """One ``Page`` element. Missing attributes are ``None``."""

    __slots__ = ("image", "image_width", "image_height", "image_size", "type")

    def __init__(
        self,
        *,
        image: str | None = None,
        image_width: str | None = None,
        image_height: str | None = None,
        image_size: str | None = None,
        type: str | None = None,
    ) -> None:
        self.image = image
        self.image_width = image_width
        self.image_height = image_height
        self.image_size = image_size
        self.type = type


class ComicInfo:
    """Owned ComicInfo fields plus the original element tree."""

    def __init__(self, root: etree._Element) -> None:
        self._root = root

    @classmethod
    def empty(cls) -> "ComicInfo":
        """Return a model with no elements."""
        return cls(etree.Element("ComicInfo"))

    @classmethod
    def from_bytes(cls, data: bytes) -> "ComicInfo":
        """Parse ComicInfo XML.

        Args:
            data: The ``ComicInfo.xml`` member bytes.

        Returns:
            A model backed by that tree.

        Raises:
            UnreadableArchiveError: The XML is empty or not a ComicInfo document.
        """
        if not data.strip():
            raise UnreadableArchiveError("ComicInfo.xml is empty")
        try:
            root = etree.fromstring(data)
        except etree.XMLSyntaxError as exc:
            raise UnreadableArchiveError("ComicInfo.xml could not be parsed") from exc
        if etree.QName(root).localname != "ComicInfo":
            raise UnreadableArchiveError("ComicInfo.xml root is not ComicInfo")
        return cls(root)

    def field_text(self, name: str) -> str | None:
        """Return an owned element's text, or ``None`` when it is absent.

        Args:
            name: An owned element name.

        Returns:
            The element text. An element with no text returns ``""``.
        """
        element = _child(self._root, name)
        if element is None:
            return None
        if element.text is None:
            return ""
        return element.text

    def pages(self) -> tuple[ComicPage, ...]:
        """Return ``Page`` entries in document order."""
        pages_el = _child(self._root, "Pages")
        if pages_el is None:
            return ()
        found: list[ComicPage] = []
        for child in pages_el:
            if etree.QName(child).localname != "Page":
                continue
            attrib = {
                etree.QName(key).localname: value for key, value in child.attrib.items()
            }
            found.append(
                ComicPage(
                    image=attrib.get("Image"),
                    image_width=attrib.get("ImageWidth"),
                    image_height=attrib.get("ImageHeight"),
                    image_size=attrib.get("ImageSize"),
                    type=attrib.get("Type"),
                )
            )
        return tuple(found)

    def apply_patch(
        self, patch: Mapping[str, str | None], *, write_number: bool
    ) -> dict[str, str | None]:
        """Apply a field patch on this tree.

        Args:
            patch: Owned element names mapped to new text, or ``None`` / ``""``
                to remove the element.
            write_number: When false, a ``Number`` entry is ignored.

        Returns:
            The fields that were actually written.

        Raises:
            ArchiveError: A key is not an owned element, or a value is not text.
        """
        applied: dict[str, str | None] = {}
        for name, value in patch.items():
            if name not in OWNED_ELEMENTS:
                raise ArchiveError(f"{name} is not a ComicInfo field")
            if name == "Number" and not write_number:
                continue
            if value is None or value == "":
                _remove_child(self._root, name)
                applied[name] = None
                continue
            if not isinstance(value, str):
                raise ArchiveError(f"{name} must be a string or None")
            _set_child_text(self._root, name, value)
            applied[name] = value
        return applied

    def to_bytes(self) -> bytes:
        """Serialize the tree, including elements this model does not edit."""
        return etree.tostring(self._root, xml_declaration=True, encoding="UTF-8")


def resolve_cover_index(
    pages: tuple[ComicPage, ...] | list[ComicPage], page_count: int
) -> int:
    """Return the reading-order cover index.

    The cover is the lowest index whose ``Page`` has ``Image`` equal to that
    index and ``Type`` equal to ``FrontCover``. Otherwise the cover is ``0``.

    Args:
        pages: ``Page`` entries from ComicInfo. A missing list is empty.
        page_count: Number of page images in the archive.

    Returns:
        The cover index. This does not read image bytes.
    """
    found: list[int] = []
    for page in pages:
        if page.type != "FrontCover" or page.image is None:
            continue
        if not page.image.isascii() or not page.image.isdigit():
            continue
        index = int(page.image)
        if index >= page_count:
            continue
        found.append(index)
    if not found:
        return 0
    return min(found)


def _child(parent: etree._Element, name: str) -> etree._Element | None:
    for child in parent:
        if etree.QName(child).localname == name:
            return child
    return None


def _remove_child(parent: etree._Element, name: str) -> None:
    child = _child(parent, name)
    if child is not None:
        parent.remove(child)


def _set_child_text(parent: etree._Element, name: str, value: str) -> None:
    child = _child(parent, name)
    if child is None:
        namespace = etree.QName(parent).namespace
        tag = f"{{{namespace}}}{name}" if namespace else name
        child = etree.SubElement(parent, tag)
    child.text = value
