using System.Text.Json;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class UpdateCheckTests
{
    private static readonly DateTimeOffset Now =
        new(2026, 8, 22, 12, 0, 0, TimeSpan.Zero);

    [Fact]
    public void Due_when_never_checked_or_a_day_has_passed()
    {
        Assert.True(UpdateCheck.IsDue(null, Now));
        Assert.True(UpdateCheck.IsDue(Now - TimeSpan.FromHours(24), Now));
        Assert.True(UpdateCheck.IsDue(Now - TimeSpan.FromDays(30), Now));
        Assert.False(UpdateCheck.IsDue(Now - TimeSpan.FromHours(23), Now));
        Assert.False(UpdateCheck.IsDue(Now, Now));
    }

    [Fact]
    public void A_stamp_far_in_the_future_does_not_silence_the_check()
    {
        // Clock jump or a hand-edited file: a stamp a day past "now" is
        // due again; one a few minutes ahead is just clock skew.
        Assert.True(UpdateCheck.IsDue(Now + TimeSpan.FromDays(2), Now));
        Assert.False(UpdateCheck.IsDue(Now + TimeSpan.FromMinutes(5), Now));
    }

    private static JsonElement? Summary(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    [Fact]
    public void Parse_reads_the_block_and_tolerates_nulls()
    {
        var s = UpdateCheck.Parse(Summary(
            """{"tools": {}, "update_check": {"consent": null, "hard_disabled": false, "current": "2.11.0", "latest": null, "newer": null, "releases_url": "https://example.invalid/r"}}"""));
        Assert.NotNull(s);
        Assert.Null(s!.Consent);
        Assert.False(s.HardDisabled);
        Assert.Equal("2.11.0", s.Current);
        Assert.Null(s.Latest);
        Assert.Null(s.Newer);
        Assert.Equal("https://example.invalid/r", s.ReleasesUrl);
    }

    [Fact]
    public void Parse_reads_a_newer_version()
    {
        var s = UpdateCheck.Parse(Summary(
            """{"update_check": {"consent": true, "hard_disabled": false, "current": "2.11.0", "latest": "2.12.0", "newer": true, "releases_url": "u"}}"""));
        Assert.Equal((true, "2.12.0", true), (s!.Consent, s.Latest, s.Newer));
    }

    [Fact]
    public void Parse_returns_null_without_the_block()
    {
        // An older CLI's doctor summary, a missing summary, a non-object:
        // nothing to act on, never a throw.
        Assert.Null(UpdateCheck.Parse(Summary("""{"tools": {}}""")));
        Assert.Null(UpdateCheck.Parse(null));
        Assert.Null(UpdateCheck.Parse(Summary("""{"update_check": 42}""")));
    }
}
