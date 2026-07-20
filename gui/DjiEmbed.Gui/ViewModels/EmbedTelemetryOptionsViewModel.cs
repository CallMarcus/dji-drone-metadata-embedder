using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>A selectable output container: a label over a CLI key.</summary>
public sealed record ContainerChoice(string Label, string Key);

/// <summary>A selectable privacy stance: a label over an <see cref="EmbedPrivacy"/>.
/// Separate from <see cref="PrivacyChoice"/>, which wraps <see cref="MapPrivacy"/>
/// and so cannot express the third stance <c>embed --redact</c> accepts.</summary>
public sealed record EmbedPrivacyChoice(string Label, EmbedPrivacy Value);

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

    public IReadOnlyList<EmbedPrivacyChoice> PrivacyOptions { get; } =
    [
        new("Keep exact locations", EmbedPrivacy.Keep),
        new("Fuzz to ~100 m", EmbedPrivacy.Fuzz),
        new("Remove GPS entirely", EmbedPrivacy.Drop),
    ];

    [ObservableProperty]
    public partial ContainerChoice SelectedContainer { get; set; }

    [ObservableProperty]
    public partial EmbedPrivacyChoice SelectedPrivacy { get; set; }

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
        SelectedPrivacy.Value == EmbedPrivacy.Drop && ExtractHome;

    partial void OnSelectedPrivacyChanged(EmbedPrivacyChoice value) =>
        OnPropertyChanged(nameof(ShowsHomeEmptiedNote));

    partial void OnExtractHomeChanged(bool value) =>
        OnPropertyChanged(nameof(ShowsHomeEmptiedNote));

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
