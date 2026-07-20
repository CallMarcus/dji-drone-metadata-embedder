using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>A selectable basemap: a friendly label over a <c>tiles.py</c> key.</summary>
public sealed record TileChoice(string Label, string Key);

/// <summary>A selectable privacy stance: a label over a <see cref="MapPrivacy"/>.</summary>
public sealed record PrivacyChoice(string Label, MapPrivacy Value);

/// <summary>
/// Observable control state for the Flight map options panel (GUI 2.0 spec,
/// M3b). Bound directly to the SukiUI-themed controls; <see cref="ToOptions"/>
/// snapshots it into the immutable <see cref="FlightMapOptions"/> the builder
/// consumes. Lives on <see cref="WorkspaceViewModel"/>; in-memory only.
/// </summary>
public partial class FlightMapOptionsViewModel : ViewModelBase
{
    public IReadOnlyList<TileChoice> TileStyles { get; } =
    [
        new("Standard", "osm"),
        new("Humanitarian", "osm-hot"),
        new("Topographic", "opentopomap"),
        new("Cycling", "cyclosm"),
    ];

    public IReadOnlyList<PrivacyChoice> PrivacyOptions { get; } =
    [
        new("Keep exact locations", MapPrivacy.Keep),
        new("Fuzz to ~100 m", MapPrivacy.Fuzz),
    ];

    [ObservableProperty]
    public partial bool Recursive { get; set; } = true;

    [ObservableProperty]
    public partial TileChoice SelectedTileStyle { get; set; }

    [ObservableProperty]
    public partial PrivacyChoice SelectedPrivacy { get; set; }

    [ObservableProperty]
    public partial int JoinGap { get; set; } = 15;

    [ObservableProperty]
    public partial bool ExportAll { get; set; }

    [ObservableProperty]
    public partial string TzOffset { get; set; } = "auto";

    [ObservableProperty]
    public partial string Title { get; set; } = "";

    [ObservableProperty]
    public partial string Output { get; set; } = "";

    public FlightMapOptionsViewModel()
    {
        SelectedTileStyle = TileStyles[0];
        SelectedPrivacy = PrivacyOptions[0];
    }

    public FlightMapOptions ToOptions() => new(
        Recursive: Recursive,
        TileStyle: SelectedTileStyle.Key,
        Privacy: SelectedPrivacy.Value,
        JoinGap: JoinGap,
        ExportAll: ExportAll,
        TzOffset: TzOffset,
        Title: Title,
        Output: Output);
}
