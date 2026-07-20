using DjiEmbed.Gui.ViewModels;

namespace DjiEmbed.Gui.Tests;

public class EmbedTelemetryOptionsViewModelTests
{
    [Fact]
    public void Defaults_match_the_embed_options_defaults()
    {
        var vm = new EmbedTelemetryOptionsViewModel();
        Assert.Equal(EmbedTelemetryOptions.Defaults, vm.ToOptions());
    }

    [Fact]
    public void Default_selections_are_mp4_and_keep_with_nothing_ticked()
    {
        var vm = new EmbedTelemetryOptionsViewModel();
        Assert.Equal("mp4", vm.SelectedContainer.Key);
        Assert.Equal(EmbedPrivacy.Keep, vm.SelectedPrivacy.Value);
        Assert.False(vm.ExtractHome);
        Assert.False(vm.UseExifTool);
        Assert.False(vm.AudioSidecar);
        Assert.False(vm.DatAuto);
        Assert.Equal("", vm.Output);
    }

    [Fact]
    public void Privacy_offers_all_three_stances_the_embed_cli_accepts()
    {
        var vm = new EmbedTelemetryOptionsViewModel();
        Assert.Equal(
            [EmbedPrivacy.Keep, EmbedPrivacy.Fuzz, EmbedPrivacy.Drop],
            vm.PrivacyOptions.Select(p => p.Value));
    }

    [Fact]
    public void Containers_offer_only_the_two_keys_the_embed_cli_accepts()
    {
        var vm = new EmbedTelemetryOptionsViewModel();
        Assert.Equal(["mp4", "mkv"], vm.Containers.Select(c => c.Key));
    }

    [Fact]
    public void ToOptions_reflects_every_mutated_control()
    {
        var vm = new EmbedTelemetryOptionsViewModel
        {
            ExtractHome = true,
            UseExifTool = true,
            AudioSidecar = true,
            DatAuto = true,
            Output = "/out/copies",
        };
        vm.SelectedContainer = vm.Containers.Single(c => c.Key == "mkv");
        vm.SelectedPrivacy =
            vm.PrivacyOptions.Single(p => p.Value == EmbedPrivacy.Drop);

        Assert.Equal(new EmbedTelemetryOptions(
            Privacy: EmbedPrivacy.Drop,
            Container: "mkv",
            ExtractHome: true,
            UseExifTool: true,
            AudioSidecar: true,
            DatAuto: true,
            Output: "/out/copies"), vm.ToOptions());
    }

    // apply_redaction (utilities.py) redacts `home` with everything else, so
    // Drop + ExtractHome writes "home": null — a combination that looks like
    // it does something and does not. The panel says so at the moment of the
    // choice.
    [Fact]
    public void Home_emptied_note_shows_only_when_dropping_and_extracting()
    {
        var vm = new EmbedTelemetryOptionsViewModel();
        Assert.False(vm.ShowsHomeEmptiedNote);          // Keep, not extracting

        vm.ExtractHome = true;
        Assert.False(vm.ShowsHomeEmptiedNote);          // Keep + extracting

        vm.SelectedPrivacy =
            vm.PrivacyOptions.Single(p => p.Value == EmbedPrivacy.Fuzz);
        Assert.False(vm.ShowsHomeEmptiedNote);          // Fuzz still records one

        vm.SelectedPrivacy =
            vm.PrivacyOptions.Single(p => p.Value == EmbedPrivacy.Drop);
        Assert.True(vm.ShowsHomeEmptiedNote);           // Drop + extracting

        vm.ExtractHome = false;
        Assert.False(vm.ShowsHomeEmptiedNote);          // Drop, nothing to empty
    }

    [Fact]
    public void Home_emptied_note_notifies_on_both_of_its_inputs()
    {
        var vm = new EmbedTelemetryOptionsViewModel();
        var notified = new List<string>();
        vm.PropertyChanged += (_, e) => notified.Add(e.PropertyName!);

        vm.SelectedPrivacy =
            vm.PrivacyOptions.Single(p => p.Value == EmbedPrivacy.Drop);
        vm.ExtractHome = true;

        Assert.Equal(2, notified.Count(
            n => n == nameof(EmbedTelemetryOptionsViewModel.ShowsHomeEmptiedNote)));
    }

    [Fact]
    public void Clear_output_resets_to_the_processed_folder_default()
    {
        var vm = new EmbedTelemetryOptionsViewModel { Output = "/out/copies" };
        vm.ClearOutputCommand.Execute(null);
        Assert.Equal("", vm.Output);
    }
}
