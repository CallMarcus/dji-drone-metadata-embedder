using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>A selectable output format: a label over a CLI format key,
/// plus the filename suffix the save dialog suggests.</summary>
public sealed record FormatChoice(string Label, string Key, string Suffix);

/// <summary>A selectable footprint lens: a label over a CLI --model key
/// (empty = the CLI's generic wide default).</summary>
public sealed record ModelChoice(string Label, string Key);

/// <summary>
/// Observable control state for the Convert options panel (GUI 2.0 spec,
/// M4a). Bound directly to the panel; <see cref="ToOptions"/> snapshots it
/// into the immutable <see cref="ConvertTelemetryOptions"/> the builder
/// consumes. Lives on <see cref="WorkspaceViewModel"/>; in-memory only.
/// </summary>
public partial class ConvertOptionsViewModel : ViewModelBase
{
    public IReadOnlyList<FormatChoice> Formats { get; } =
    [
        new("GPX track", "gpx", "gpx"),
        new("CSV spreadsheet", "csv", "csv"),
        new("GeoJSON", "geojson", "geojson"),
        new("KML (Google Earth)", "kml", "kml"),
        new("Web map (HTML)", "html", "html"),
        new("CoT (ATAK/WinTAK)", "cot", "cot.xml"),
    ];

    public IReadOnlyList<TelemetryPrivacyChoice> PrivacyOptions { get; } =
    [
        new("Keep exact locations", TelemetryPrivacy.Keep),
        new("Fuzz to ~100 m", TelemetryPrivacy.Fuzz),
        new("Remove GPS entirely", TelemetryPrivacy.Drop),
    ];

    public IReadOnlyList<ModelChoice> Models { get; } =
    [
        new("Generic wide lens (default)", ""),
        new("DJI Air 3", "air3"),
        new("DJI Avata 2", "avata2"),
        new("DJI Mini 4 Pro", "mini4pro"),
        new("DJI Avata 360", "avata360"),
    ];

    [ObservableProperty]
    public partial FormatChoice SelectedFormat { get; set; }

    [ObservableProperty]
    public partial TelemetryPrivacyChoice SelectedPrivacy { get; set; }

    [ObservableProperty]
    public partial string TzOffset { get; set; } = "";

    [ObservableProperty]
    public partial bool Footprints { get; set; }

    [ObservableProperty]
    public partial double FootprintInterval { get; set; } = 2;

    [ObservableProperty]
    public partial ModelChoice SelectedModel { get; set; }

    [ObservableProperty]
    public partial double CotInterval { get; set; } = 1;

    [ObservableProperty]
    public partial string CotType { get; set; } = "a-n-A";

    [ObservableProperty]
    public partial string Output { get; set; } = "";

    public ConvertOptionsViewModel()
    {
        SelectedFormat = Formats[0];
        SelectedPrivacy = PrivacyOptions[0];
        SelectedModel = Models[0];
    }

    /// <summary>Footprint controls apply to GeoJSON/KML only — the other
    /// formats have no polygon to carry.</summary>
    public bool ShowsFootprintOptions =>
        SelectedFormat.Key is "geojson" or "kml";

    /// <summary>CoT sampling controls apply to CoT only.</summary>
    public bool ShowsCotOptions => SelectedFormat.Key == "cot";

    /// <summary>
    /// True when footprints are requested but the privacy stance silently
    /// suppresses them: the CLI drops footprints under any redaction — a
    /// precise polygon would re-sharpen a fuzzed centre — and says nothing.
    /// A real property (not a XAML multi-binding) so it is assertable
    /// headless.
    /// </summary>
    public bool ShowsFootprintsSuppressedNote =>
        Footprints && ShowsFootprintOptions
        && SelectedPrivacy.Value != TelemetryPrivacy.Keep;

    partial void OnSelectedFormatChanged(FormatChoice value)
    {
        OnPropertyChanged(nameof(ShowsFootprintOptions));
        OnPropertyChanged(nameof(ShowsCotOptions));
        OnPropertyChanged(nameof(ShowsFootprintsSuppressedNote));
    }

    partial void OnFootprintsChanged(bool value) =>
        OnPropertyChanged(nameof(ShowsFootprintsSuppressedNote));

    partial void OnSelectedPrivacyChanged(TelemetryPrivacyChoice value) =>
        OnPropertyChanged(nameof(ShowsFootprintsSuppressedNote));

    public ConvertTelemetryOptions ToOptions() => new(
        Format: SelectedFormat.Key,
        Privacy: SelectedPrivacy.Value,
        TzOffset: TzOffset,
        Footprints: Footprints,
        FootprintInterval: FootprintInterval,
        Model: SelectedModel.Key,
        CotInterval: CotInterval,
        CotType: CotType,
        Output: Output);

    /// <summary>Reset the output override back to the default (beside the
    /// source file).</summary>
    [RelayCommand]
    private void ClearOutput() => Output = "";
}
