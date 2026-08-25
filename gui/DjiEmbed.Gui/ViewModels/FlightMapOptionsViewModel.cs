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
    public partial bool Airspace { get; set; }

    [ObservableProperty]
    public partial int JoinGap { get; set; } = 15;

    [ObservableProperty]
    public partial bool LinkOriginals { get; set; }

    [ObservableProperty]
    public partial bool GimbalFromVideo { get; set; }

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

    /// <summary>
    /// True exactly while <c>--airspace</c> is in the emitted argv, so the
    /// network-disclosure note never claims a fetch for a run that makes
    /// none (#427, tightened by the #431 review). 3D stopped mattering when
    /// the builder let the pair through (#530). A real property so it is
    /// assertable headless.
    /// </summary>
    public bool ShowsAirspaceNote =>
        Airspace && SelectedPrivacy.Value != MapPrivacy.Fuzz;

    /// <summary>
    /// True when the airspace checkbox is ticked but the builder keeps
    /// <c>--airspace</c> out of the argv because Fuzz privacy is on (the
    /// CLI rejects the pair — zones checked against coarsened coordinates
    /// would mislead). Flat or 3D alike, now that Fuzz is the only
    /// suppression left (#427, #530). A real property so it is assertable
    /// headless.
    /// </summary>
    public bool ShowsAirspaceFuzzNote =>
        Airspace && SelectedPrivacy.Value == MapPrivacy.Fuzz;

    /// <summary>
    /// True exactly while "Export all" will write the flight record — which
    /// itself fetches airspace and terrain data, a fetch the CLI announces
    /// only on stderr where the GUI discards it on success, so the panel
    /// must disclose it up front (#431 review).
    /// </summary>
    public bool ShowsRecordNetworkNote =>
        ExportAll && !ThreeD && SelectedPrivacy.Value != MapPrivacy.Fuzz;

    /// <summary>
    /// True when "Export all" runs without the flight record: under Fuzz
    /// the CLI deliberately skips <c>flight-record.html</c> (a record
    /// built on coarsened coordinates would mislead), and the note
    /// pre-empts the missing-file surprise. Quiet under 3D, where the
    /// export is suppressed entirely (#427).
    /// </summary>
    public bool ShowsRecordSkipNote =>
        ExportAll && !ThreeD && SelectedPrivacy.Value == MapPrivacy.Fuzz;

    partial void OnThreeDChanged(bool value)
    {
        OnPropertyChanged(nameof(ShowsFuzzCaveat));
        OnPropertyChanged(nameof(ShowsRecordNetworkNote));
        OnPropertyChanged(nameof(ShowsRecordSkipNote));
    }

    partial void OnLinkOriginalsChanged(bool value) =>
        OnPropertyChanged(nameof(ShowsFuzzCaveat));

    partial void OnAirspaceChanged(bool value)
    {
        OnPropertyChanged(nameof(ShowsAirspaceNote));
        OnPropertyChanged(nameof(ShowsAirspaceFuzzNote));
    }

    partial void OnExportAllChanged(bool value)
    {
        OnPropertyChanged(nameof(ShowsRecordNetworkNote));
        OnPropertyChanged(nameof(ShowsRecordSkipNote));
    }

    partial void OnSelectedPrivacyChanged(PrivacyChoice value)
    {
        OnPropertyChanged(nameof(ShowsFuzzCaveat));
        OnPropertyChanged(nameof(ShowsAirspaceNote));
        OnPropertyChanged(nameof(ShowsAirspaceFuzzNote));
        OnPropertyChanged(nameof(ShowsRecordNetworkNote));
        OnPropertyChanged(nameof(ShowsRecordSkipNote));
    }

    public FlightMapOptions ToOptions() => new(
        Recursive: Recursive,
        ThreeD: ThreeD,
        TileStyle: SelectedTileStyle.Key,
        Privacy: SelectedPrivacy.Value,
        Airspace: Airspace,
        JoinGap: JoinGap,
        LinkOriginals: LinkOriginals,
        ExportAll: ExportAll,
        TzOffset: TzOffset,
        Title: Title,
        Output: Output,
        GimbalFromVideo: GimbalFromVideo);

    /// <summary>Reset the output override back to the default (write the map
    /// into the source folder).</summary>
    [RelayCommand]
    private void ClearOutput() => Output = "";
}
