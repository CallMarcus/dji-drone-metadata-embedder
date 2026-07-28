using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace DjiEmbed.Gui.ViewModels;

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
    public IReadOnlyList<TileChoice> TileStyles { get; } = TileChoice.All;

    public IReadOnlyList<PrivacyChoice> PrivacyOptions { get; } =
    [
        new("Keep exact locations", MapPrivacy.Keep),
        new("Fuzz to ~100 m", MapPrivacy.Fuzz),
    ];

    [ObservableProperty]
    public partial bool Recursive { get; set; } = true;

    [ObservableProperty]
    public partial bool ThreeD { get; set; }

    [ObservableProperty]
    public partial TileChoice SelectedTileStyle { get; set; }

    [ObservableProperty]
    public partial PrivacyChoice SelectedPrivacy { get; set; }

    [ObservableProperty]
    public partial int JoinGap { get; set; } = 15;

    [ObservableProperty]
    public partial bool LinkOriginals { get; set; }

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

    /// <summary>
    /// True when the emitted argv will pair <c>--link-originals</c> with
    /// <c>--redact fuzz</c> — the 3D map keeps the links but withholds the
    /// video blend, because coarsened coordinates cannot honestly be
    /// compared against real footage. Mirrors the photo map's caveat
    /// (which the CLI prints only to stderr, where the GUI discards it on
    /// success); gated on ThreeD because without it the builder suppresses
    /// the flag entirely (#392). A real property so it is assertable
    /// headless.
    /// </summary>
    public bool ShowsFuzzCaveat =>
        ThreeD && LinkOriginals && SelectedPrivacy.Value == MapPrivacy.Fuzz;

    partial void OnThreeDChanged(bool value) =>
        OnPropertyChanged(nameof(ShowsFuzzCaveat));

    partial void OnLinkOriginalsChanged(bool value) =>
        OnPropertyChanged(nameof(ShowsFuzzCaveat));

    partial void OnSelectedPrivacyChanged(PrivacyChoice value) =>
        OnPropertyChanged(nameof(ShowsFuzzCaveat));

    public FlightMapOptions ToOptions() => new(
        Recursive: Recursive,
        ThreeD: ThreeD,
        TileStyle: SelectedTileStyle.Key,
        Privacy: SelectedPrivacy.Value,
        JoinGap: JoinGap,
        LinkOriginals: LinkOriginals,
        ExportAll: ExportAll,
        TzOffset: TzOffset,
        Title: Title,
        Output: Output);

    /// <summary>Reset the output override back to the default (write the map
    /// into the source folder).</summary>
    [RelayCommand]
    private void ClearOutput() => Output = "";
}
