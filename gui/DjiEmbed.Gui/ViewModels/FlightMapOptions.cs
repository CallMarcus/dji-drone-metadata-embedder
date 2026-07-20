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
/// <param name="TileStyle">A <c>tiles.py</c> key: <c>osm</c> (default),
/// <c>osm-hot</c>, <c>opentopomap</c>, or <c>cyclosm</c>.</param>
/// <param name="JoinGap">Seconds to chain size-split recordings; 15 = the CLI
/// default, 0 = don't join.</param>
/// <param name="ExportAll">Also write KML + GeoJSON (<c>--format all</c>); the
/// CLI format is single-valued, so this is one honest toggle, not per-format.</param>
/// <param name="TzOffset"><c>auto</c> (default) or an explicit UTC offset.</param>
public sealed record FlightMapOptions(
    bool Recursive,
    string TileStyle,
    MapPrivacy Privacy,
    int JoinGap,
    bool ExportAll,
    string TzOffset,
    string Title,
    string Output)
{
    public static readonly FlightMapOptions Defaults = new(
        Recursive: true,
        TileStyle: "osm",
        Privacy: MapPrivacy.Keep,
        JoinGap: 15,
        ExportAll: false,
        TzOffset: "auto",
        Title: "",
        Output: "");
}
