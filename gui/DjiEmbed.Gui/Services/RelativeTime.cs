using System;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Ages in words for on-screen timestamps ("2 days ago"). Takes "now" as a
/// parameter rather than reading the clock, so it stays pure and testable;
/// the view's converter supplies <c>DateTime.UtcNow</c> at bind time.
/// </summary>
public static class RelativeTime
{
    public static string Describe(DateTime whenUtc, DateTime nowUtc)
    {
        var age = nowUtc - whenUtc;
        if (age < TimeSpan.FromMinutes(1))
        {
            return "just now";
        }
        if (age < TimeSpan.FromHours(1))
        {
            return Ago((int)age.TotalMinutes, "minute");
        }
        if (age < TimeSpan.FromDays(1))
        {
            return Ago((int)age.TotalHours, "hour");
        }
        return Ago((int)age.TotalDays, "day");
    }

    private static string Ago(int count, string unit) =>
        count == 1 ? $"1 {unit} ago" : $"{count} {unit}s ago";
}
