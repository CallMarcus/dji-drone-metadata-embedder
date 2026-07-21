using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>A selectable output container: a label over a CLI key.</summary>
public sealed record ContainerChoice(string Label, string Key);

/// <summary>
/// Observable control state for the Embed telemetry options panel (GUI 2.0
/// spec, M3d). Bound directly to the SukiUI-themed controls;
/// <see cref="ToOptions"/> snapshots it into the immutable
/// <see cref="EmbedTelemetryOptions"/> the builder consumes. Lives on
/// <see cref="WorkspaceViewModel"/>; in-memory only.
/// </summary>
public partial class EmbedTelemetryOptionsViewModel : ViewModelBase
{
    public IReadOnlyList<ContainerChoice> Containers { get; } =
    [
        new("MP4 (most compatible)", "mp4"),
        new("MKV (keeps DJI data streams)", "mkv"),
    ];

    public IReadOnlyList<TelemetryPrivacyChoice> PrivacyOptions { get; } =
    [
        new("Keep exact locations", TelemetryPrivacy.Keep),
        new("Fuzz to ~100 m", TelemetryPrivacy.Fuzz),
        new("Remove GPS entirely", TelemetryPrivacy.Drop),
    ];

    [ObservableProperty]
    public partial ContainerChoice SelectedContainer { get; set; }

    [ObservableProperty]
    public partial TelemetryPrivacyChoice SelectedPrivacy { get; set; }

    [ObservableProperty]
    public partial bool ExtractHome { get; set; }

    [ObservableProperty]
    public partial bool UseExifTool { get; set; }

    [ObservableProperty]
    public partial bool AudioSidecar { get; set; }

    [ObservableProperty]
    public partial bool DatAuto { get; set; }

    [ObservableProperty]
    public partial string Output { get; set; } = "";

    public EmbedTelemetryOptionsViewModel()
    {
        SelectedContainer = Containers[0];
        SelectedPrivacy = PrivacyOptions[0];
    }

    /// <summary>
    /// True when the launch point is requested but the privacy stance empties
    /// it. <c>apply_redaction</c> (<c>utilities.py</c>) redacts <c>home</c>
    /// alongside the coordinates, so <c>drop</c> writes <c>"home": null</c> —
    /// the option looks active and achieves nothing. A real property (not a
    /// XAML multi-binding) so it is assertable headless.
    /// </summary>
    public bool ShowsHomeEmptiedNote =>
        SelectedPrivacy.Value == TelemetryPrivacy.Drop && ExtractHome;

    partial void OnSelectedPrivacyChanged(TelemetryPrivacyChoice value) =>
        OnPropertyChanged(nameof(ShowsHomeEmptiedNote));

    partial void OnExtractHomeChanged(bool value) =>
        OnPropertyChanged(nameof(ShowsHomeEmptiedNote));

    /// <summary>
    /// True when ExifTool is requested but the chosen container makes it a
    /// no-op. ExifTool cannot write Matroska (<c>exiftool -listwf</c> lists
    /// MP4/MOV, not MKV), and <c>embedder.py:735</c> discards the failed
    /// call's return value — so the run reports success and writes no tags.
    /// A real property (not a XAML multi-binding) so it is assertable headless.
    /// </summary>
    public bool ShowsExifToolMkvNote =>
        UseExifTool && SelectedContainer.Key == "mkv";

    partial void OnUseExifToolChanged(bool value) =>
        OnPropertyChanged(nameof(ShowsExifToolMkvNote));

    partial void OnSelectedContainerChanged(ContainerChoice value) =>
        OnPropertyChanged(nameof(ShowsExifToolMkvNote));

    public EmbedTelemetryOptions ToOptions() => new(
        Privacy: SelectedPrivacy.Value,
        Container: SelectedContainer.Key,
        ExtractHome: ExtractHome,
        UseExifTool: UseExifTool,
        AudioSidecar: AudioSidecar,
        DatAuto: DatAuto,
        Output: Output);

    /// <summary>Reset the output override back to the default (a
    /// <c>processed</c> folder inside the source folder).</summary>
    [RelayCommand]
    private void ClearOutput() => Output = "";
}
