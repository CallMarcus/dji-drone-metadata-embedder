namespace DjiEmbed.Gui.ViewModels;

/// <summary>How the Flight map treats GPS coordinates. Mirrors the two
/// values <c>flightmap --redact</c> accepts (there is no "drop" for maps).</summary>
public enum MapPrivacy
{
    Keep,
    Fuzz,
}

/// <summary>
/// Immutable, typed state for a Flight map run (GUI 2.0 spec, M3b). It is the
/// single input to <see cref="Services.CommandBuilder.FlightMap"/>, so the argv
/// is a pure function of this record — golden-testable. Every field maps to an
/// existing <c>flightmap</c> flag; defaults reproduce M3a's hardcoded argv.
/// </summary>
/// <param name="ThreeD">Write the MapLibre 3D terrain map
/// (<c>flightmap-3d.html</c>) instead of the flat map. The CLI ignores
/// <c>--tile-style</c> and rejects <c>--format all</c> with <c>--3d</c>,
/// so the builder suppresses both while this is set.</param>
/// <param name="TileStyle">A <c>tiles.py</c> key: <c>osm</c> (default),
/// <c>osm-hot</c>, <c>opentopomap</c>, or <c>cyclosm</c>.</param>
/// <param name="JoinGap">Seconds to chain size-split recordings; 15 = the CLI
/// default, 0 = don't join.</param>
/// <param name="LinkOriginals">Embed links to each flight's source videos
/// (<c>--link-originals</c>), which the 3D cockpit's video crossfade needs.
/// Only useful with <paramref name="ThreeD"/> — on the flat map the CLI
/// warns it embeds dead weight — so the builder emits it only alongside
/// <c>--3d</c> (#392).</param>
/// <param name="ExportAll">Also write KML + GeoJSON (<c>--format all</c>); the
/// CLI format is single-valued, so this is one honest toggle, not per-format.</param>
/// <param name="TzOffset"><c>auto</c> (default) or an explicit UTC offset.</param>
public sealed record FlightMapOptions(
    bool Recursive,
    bool ThreeD,
    string TileStyle,
    MapPrivacy Privacy,
    int JoinGap,
    bool LinkOriginals,
    bool ExportAll,
    string TzOffset,
    string Title,
    string Output)
{
    public static readonly FlightMapOptions Defaults = new(
        Recursive: true,
        ThreeD: false,
        TileStyle: "osm",
        Privacy: MapPrivacy.Keep,
        JoinGap: 15,
        LinkOriginals: false,
        ExportAll: false,
        TzOffset: "auto",
        Title: "",
        Output: "");
}
