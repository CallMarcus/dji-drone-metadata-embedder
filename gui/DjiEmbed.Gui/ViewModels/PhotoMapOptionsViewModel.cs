using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// Observable control state for the Photo map options panel (GUI 2.0 spec,
/// M3c). Bound directly to the SukiUI-themed controls; <see cref="ToOptions"/>
/// snapshots it into the immutable <see cref="PhotoMapOptions"/> the builder
/// consumes. Lives on <see cref="WorkspaceViewModel"/>; in-memory only.
/// </summary>
public partial class PhotoMapOptionsViewModel : ViewModelBase
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
    public partial TileChoice SelectedTileStyle { get; set; }

    [ObservableProperty]
    public partial PrivacyChoice SelectedPrivacy { get; set; }

    [ObservableProperty]
    public partial bool LinkOriginals { get; set; } = true;

    [ObservableProperty]
    public partial bool ShowName { get; set; } = true;

    [ObservableProperty]
    public partial bool ShowTimestamp { get; set; } = true;

    [ObservableProperty]
    public partial bool ShowCamera { get; set; } = true;

    [ObservableProperty]
    public partial bool ShowAltitude { get; set; } = true;

    [ObservableProperty]
    public partial bool ShowCredit { get; set; } = true;

    [ObservableProperty]
    public partial bool ExportAll { get; set; }

    [ObservableProperty]
    public partial string Title { get; set; } = "";

    [ObservableProperty]
    public partial string Output { get; set; } = "";

    public PhotoMapOptionsViewModel()
    {
        SelectedTileStyle = TileStyles[0];
        SelectedPrivacy = PrivacyOptions[0];
    }

    /// <summary>
    /// True when the map coordinates are fuzzed but the popups still link the
    /// originals — whose EXIF keeps the exact GPS. Mirrors the note the CLI
    /// prints on stderr, which the GUI folds into the warnings area. A real
    /// property (not a XAML multi-binding) so it is assertable headless.
    /// </summary>
    public bool ShowsFuzzCaveat =>
        SelectedPrivacy.Value == MapPrivacy.Fuzz && LinkOriginals;

    partial void OnSelectedPrivacyChanged(PrivacyChoice value) =>
        OnPropertyChanged(nameof(ShowsFuzzCaveat));

    partial void OnLinkOriginalsChanged(bool value) =>
        OnPropertyChanged(nameof(ShowsFuzzCaveat));

    public PhotoMapOptions ToOptions() => new(
        Recursive: Recursive,
        TileStyle: SelectedTileStyle.Key,
        Privacy: SelectedPrivacy.Value,
        LinkOriginals: LinkOriginals,
        Popup: new PopupFields(
            Name: ShowName,
            Timestamp: ShowTimestamp,
            Camera: ShowCamera,
            Altitude: ShowAltitude,
            Credit: ShowCredit),
        ExportAll: ExportAll,
        Title: Title,
        Output: Output);

    /// <summary>Reset the output override back to the default (write the map
    /// into the source folder).</summary>
    [RelayCommand]
    private void ClearOutput() => Output = "";
}
