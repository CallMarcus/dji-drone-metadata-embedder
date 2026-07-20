using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class RelativeTimeTests
{
    private static readonly DateTime Now =
        new(2026, 7, 20, 12, 0, 0, DateTimeKind.Utc);

    [Theory]
    [InlineData(-5, "just now")]        // clock skew: stamped in the future
    [InlineData(0, "just now")]
    [InlineData(0.9, "just now")]
    [InlineData(1, "1 minute ago")]
    [InlineData(59, "59 minutes ago")]
    [InlineData(60, "1 hour ago")]
    [InlineData(175, "2 hours ago")]    // 2 h 55 m truncates down
    [InlineData(1439, "23 hours ago")]
    [InlineData(1440, "1 day ago")]
    [InlineData(2880, "2 days ago")]
    [InlineData(412 * 24 * 60, "412 days ago")]
    public void Describes_the_age_in_the_largest_whole_unit(
        double minutesAgo, string expected)
    {
        Assert.Equal(expected,
            RelativeTime.Describe(Now.AddMinutes(-minutesAgo), Now));
    }
}
