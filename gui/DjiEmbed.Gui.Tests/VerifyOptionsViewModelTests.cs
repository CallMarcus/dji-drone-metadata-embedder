using DjiEmbed.Gui.ViewModels;
using Xunit;

namespace DjiEmbed.Gui.Tests;

public class VerifyOptionsViewModelTests
{
    [Fact]
    public void Defaults_are_check_with_cli_default_drift_and_auto_tz()
    {
        var vm = new VerifyOptionsViewModel();
        Assert.Equal(VerifyTelemetryOptions.Defaults, vm.ToOptions());
        Assert.True(vm.IsCheck);
        Assert.False(vm.IsValidate);
        Assert.False(vm.IsSun);
    }

    [Fact]
    public void Radio_bools_drive_and_reflect_the_sub_action()
    {
        var vm = new VerifyOptionsViewModel();
        vm.IsValidate = true;
        Assert.Equal(VerifySubAction.Validate, vm.SubAction);
        Assert.False(vm.IsCheck);
        // The OLD radio turning off must not steal the selection back.
        vm.IsCheck = false;
        Assert.Equal(VerifySubAction.Validate, vm.SubAction);
        vm.IsSun = true;
        Assert.Equal(VerifySubAction.Sun, vm.SubAction);
    }

    [Fact]
    public void Contextual_gates_follow_the_sub_action()
    {
        var vm = new VerifyOptionsViewModel();
        Assert.False(vm.ShowsDriftOptions);
        Assert.False(vm.ShowsTzOptions);
        Assert.False(vm.ShowsAdvancedOptions);
        vm.SubAction = VerifySubAction.Validate;
        Assert.True(vm.ShowsDriftOptions);
        Assert.False(vm.ShowsTzOptions);
        Assert.True(vm.ShowsAdvancedOptions);
        vm.SubAction = VerifySubAction.Sun;
        Assert.False(vm.ShowsDriftOptions);
        Assert.True(vm.ShowsTzOptions);
        Assert.True(vm.ShowsAdvancedOptions);
    }

    [Fact]
    public void ToOptions_snapshots_the_control_state()
    {
        var vm = new VerifyOptionsViewModel
        {
            SubAction = VerifySubAction.Validate,
            DriftThreshold = 2.5,
            TzOffset = "+02:00",
        };
        Assert.Equal(
            new VerifyTelemetryOptions(VerifySubAction.Validate, 2.5, "+02:00"),
            vm.ToOptions());
    }
}
