namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// Which details the HTML popups may show. Mirrors <c>POPUP_FIELDS</c> in
/// <c>geo/photomap_html.py</c>; an unticked field is left out of the map file
/// entirely (the photos themselves are never modified).
/// </summary>
public sealed record PopupFields(
    bool Name,
    bool Timestamp,
    bool Camera,
    bool Altitude,
    bool Credit)
{
    /// <summary>Every detail — the CLI default, encoded by omitting the flag.</summary>
    public static readonly PopupFields All = new(true, true, true, true, true);

    /// <summary>No details — encoded as <c>--popup-fields none</c>.</summary>
    public static readonly PopupFields None =
        new(false, false, false, false, false);
}

/// <summary>
/// Immutable, typed state for a Photo map run (GUI 2.0 spec, M3c). It is the
/// single input to <see cref="Services.CommandBuilder.PhotoMap"/>, so the argv
/// is a pure function of this record — golden-testable. Every field maps to an
/// existing <c>photomap</c> flag; defaults reproduce M3a's hardcoded argv.
/// Reuses <see cref="MapPrivacy"/>, whose two values are exactly the
/// <c>none</c>/<c>fuzz</c> that <c>photomap --redact</c> accepts.
/// </summary>
/// <param name="TileStyle">A <c>tiles.py</c> key: <c>osm</c> (default),
/// <c>osm-hot</c>, <c>opentopomap</c>, or <c>cyclosm</c>.</param>
/// <param name="LinkOriginals">Popups link the thumbnail to the photo file.
/// On by default: it is what powers the embedded 360° panorama viewer (#305).
/// Off produces a self-contained map with no local paths in it.</param>
/// <param name="ExportAll">Also write KML + GeoJSON (<c>--format all</c>); the
/// CLI format is single-valued, so this is one honest toggle, not per-format.</param>
public sealed record PhotoMapOptions(
    bool Recursive,
    string TileStyle,
    MapPrivacy Privacy,
    bool LinkOriginals,
    PopupFields Popup,
    bool ExportAll,
    string Title,
    string Output)
{
    public static readonly PhotoMapOptions Defaults = new(
        Recursive: true,
        TileStyle: "osm",
        Privacy: MapPrivacy.Keep,
        LinkOriginals: true,
        Popup: PopupFields.All,
        ExportAll: false,
        Title: "",
        Output: "");
}
