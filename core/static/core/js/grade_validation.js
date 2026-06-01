/**
 * Shared grade band validation utility functions.
 */

function getGradeForPercentage(pct, isMLevel) {
    if (pct >= 70) return "1st";
    if (pct >= 60) return "2:1";
    if (pct >= 50) return "2:2";
    if (pct >= 40 && !isMLevel) return "3rd";
    return "Fail";
}

function getExpectedBaseGrade(gradeName) {
    if (gradeName.includes("1st") || gradeName.includes("Dist")) return "1st";
    if (gradeName.includes("2:1") || gradeName.includes("Merit")) return "2:1";
    if (gradeName.includes("2:2") || gradeName.includes("Pass")) return "2:2";
    if (gradeName.includes("3rd")) return "3rd";
    return "Fail";
}
