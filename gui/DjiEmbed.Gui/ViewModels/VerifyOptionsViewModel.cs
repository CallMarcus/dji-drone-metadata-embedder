using CommunityToolkit.Mvvm.ComponentModel;

namespace DjiEmbed.Gui.ViewModels;

/// <summary>
/// Observable control state for the Verify options panel (GUI 2.0 spec,
/// M4b). Bound directly to the panel; <see cref="ToOptions"/> snapshots
/// it into the immutable <see cref="VerifyTelemetryOptions"/> the builder
/// consumes. Lives on <see cref="WorkspaceViewModel"/>; in-memory only.
/// The three radio-shaped booleans exist because a RadioButton binds a
/// bool, not an enum member; their setters ignore <c>false</c> (the old
/// radio switching off) so only the newly picked segment writes
/// <see cref="SubAction"/>.
/// </summary>
public partial class VerifyOptionsViewModel : ViewModelBase
{
    [ObservableProperty]
    public partial VerifySubAction SubAction { get; set; }
        = VerifySubAction.Check;

    [ObservableProperty]
    public partial double DriftThreshold { get; set; } = 1.0;

    [ObservableProperty]
    public partial string TzOffset { get; set; } = "";

    public bool IsCheck
    {
        get => SubAction == VerifySubAction.Check;
        set { if (value) { SubAction = VerifySubAction.Check; } }
    }

    public bool IsValidate
    {
        get => SubAction == VerifySubAction.Validate;
        set { if (value) { SubAction = VerifySubAction.Validate; } }
    }

    public bool IsSun
    {
        get => SubAction == VerifySubAction.Sun;
        set { if (value) { SubAction = VerifySubAction.Sun; } }
    }

    /// <summary>The drift slider applies to Validate pairing only.</summary>
    public bool ShowsDriftOptions => SubAction == VerifySubAction.Validate;

    /// <summary>The timezone box applies to Sun check only.</summary>
    public bool ShowsTzOptions => SubAction == VerifySubAction.Sun;

    /// <summary>Check metadata has no advanced options at all — showing
    /// an empty expander would promise settings that aren't there.</summary>
    public bool ShowsAdvancedOptions => SubAction != VerifySubAction.Check;

    partial void OnSubActionChanged(VerifySubAction value)
    {
        OnPropertyChanged(nameof(IsCheck));
        OnPropertyChanged(nameof(IsValidate));
        OnPropertyChanged(nameof(IsSun));
        OnPropertyChanged(nameof(ShowsDriftOptions));
        OnPropertyChanged(nameof(ShowsTzOptions));
        OnPropertyChanged(nameof(ShowsAdvancedOptions));
    }

    public VerifyTelemetryOptions ToOptions() => new(
        SubAction: SubAction,
        DriftThreshold: DriftThreshold,
        TzOffset: TzOffset);
}
