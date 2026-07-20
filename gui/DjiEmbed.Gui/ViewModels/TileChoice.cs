using System.Collections.Generic;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>A selectable basemap: a friendly label over a <c>tiles.py</c> key.</summary>
public sealed record TileChoice(string Label, string Key)
{
    /// <summary>
    /// The basemaps every map mode offers (GUI 2.0 spec, M3c). Flight map and
    /// Photo map take the identical <c>--tile-style</c> keys, so they share one
    /// list rather than two that can drift. Index 0 is the CLI default
    /// (<c>osm</c>), which the options ViewModels select at construction.
    /// </summary>
    public static IReadOnlyList<TileChoice> All { get; } =
    [
        new("Standard", "osm"),
        new("Humanitarian", "osm-hot"),
        new("Topographic", "opentopomap"),
        new("Cycling", "cyclosm"),
    ];
}
