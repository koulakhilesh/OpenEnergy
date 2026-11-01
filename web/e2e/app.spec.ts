import { expect, test } from "@playwright/test";

test("the simulator plays Britain's grid and plans the battery", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("20 January 2025");
  await expect(page.locator(".answer")).toContainText("of what perfect foresight allows", { timeout: 30_000 });
  await expect(page.getByRole("img", { name: /Britain used/ })).toBeVisible();
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page).toHaveURL(/\/\?day=2025-01-2\d&hour=\d+/);
  await page.getByText("Sources and licences").click();
  await expect(page.getByText(/Ember, European Wholesale Electricity Price Data/)).toBeVisible();
});

test("the Battery Lab's address opens the simulator on its day and solves the year", async ({ page }) => {
  await page.goto("/lab?year=2025&day=2025-01-21");
  await expect(page).toHaveURL(/\/\?day=2025-01-21/);
  await expect(page.locator(".answer")).toContainText("Tue, 21 January 2025", { timeout: 30_000 });
  await expect(page.getByText(/daily plans solved in/)).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "4 h" }).click();
  await expect(page).toHaveURL(/h=4/);
  await expect(page.locator(".answer")).toContainText("1 MW / 4 MWh");
});

test("keys and the year strip move the clock", async ({ page }) => {
  await page.goto("/?day=2025-06-01&hour=10");
  const clock = page.getByRole("heading", { level: 1 });
  await expect(clock).toContainText("1 June 2025 · 10:00");
  await page.keyboard.press("ArrowRight");
  await expect(clock).toContainText("11:00");
  await page.keyboard.press("Shift+ArrowRight");
  await expect(clock).toContainText("2 June 2025 · 11:00");
  const strip = page.locator(".year-strip");
  const box = (await strip.boundingBox())!;
  await page.mouse.click(box.x + 3, box.y + box.height / 2);
  await expect(clock).toContainText("January 2025");
});

test("beat the battery scores a plan as the day runs", async ({ page }) => {
  await page.goto("/play?d=2024-03-12");
  const cells = page.getByRole("group", { name: "Your plan, hour by hour" }).getByRole("button");
  await expect(cells).toHaveCount(24, { timeout: 30_000 });
  await cells.nth(3).click(); // charge to full
  await cells.nth(18).click(); // full, so the first tap sells
  await expect(cells.nth(18)).toHaveAccessibleName("18:00 sell");
  await cells.nth(5).focus();
  await page.keyboard.press("Enter"); // full: a tap from the keyboard sells too
  await expect(cells.nth(5)).toHaveAccessibleName("05:00 sell");
  await cells.nth(5).focus();
  await page.keyboard.press("Enter");
  await expect(cells.nth(5)).toHaveAccessibleName("05:00 rest");
  await page.getByRole("button", { name: "Run the day ▶" }).click();
  await expect(page.locator(".scoreboard")).toContainText("Optimiser, same forecast");
  await expect(page.getByRole("status").filter({ hasText: /optimiser/ })).toBeVisible({ timeout: 10_000 });
});

test("2035 answers from the saturation study", async ({ page }) => {
  await page.goto("/2035");
  await expect(page.locator(".answer")).toContainText("GW of batteries", { timeout: 30_000 });
  await page.getByRole("button", { name: "Falling Behind" }).click();
  await expect(page.locator(".answer")).toContainText("Falling Behind 2035");
  await expect(page).toHaveURL(/pathway=Falling\+Behind/);
});

test("research leads to the analyst pages", async ({ page }) => {
  await page.goto("/research");
  await page.getByRole("link", { name: /Value a battery/ }).click();
  await expect(page).toHaveURL(/\/run$/);
  await expect(page.getByRole("link", { name: "Research" })).toHaveAttribute("aria-current", "page");
});

test("real batteries compare the fleet with the optimiser and filter by zone", async ({ page }) => {
  await page.goto("/fleet?year=2024");
  await expect(page.locator(".answer")).toContainText("battery units ran", { timeout: 30_000 });
  const rows = page.locator("tbody tr");
  const all = await rows.count();
  expect(all).toBeGreaterThan(5);
  await page.getByRole("button", { name: "Scotland" }).click();
  await expect(rows.first().locator("td").last()).toHaveText("Scotland");
  expect(await rows.count()).toBeLessThan(all);
});

test("the docs widget plans dragged prices", async ({ page }) => {
  await page.goto("/embed/arbitrage");
  await expect(page.getByText(/plan earns/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Flatten" }).click();
  await expect(page.getByText(/plan earns £0/)).toBeVisible();
});

test("year form runs a precomputed battery and answers first", async ({ page }) => {
  await page.goto("/run");
  await expect(page.getByRole("heading", { name: "Value a battery" })).toBeVisible();
  await page.getByLabel("Historic year").selectOption("2024");
  await page.getByLabel("Power (MW)").fill("10");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page).toHaveURL(/\/result\?.*year=2024/);
  await expect(page.locator(".answer")).toContainText(
    "10 MW, 2-hour battery trading GB day-ahead prices in 2024",
  );
  await expect(page.locator(".answer")).toContainText("£290,000 a year");
  await expect(page.locator(".plot .main-svg").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Daily revenue (CSV)" })).toHaveAttribute(
    "href",
    /\/download\/daily\.csv\?.*power_mw=10/,
  );
});

test("choosing a pathway switches the source", async ({ page }) => {
  await page.goto("/run");
  await page.getByRole("combobox", { name: "FES pathway" }).selectOption("Falling Behind");
  await expect(page.getByRole("radio", { name: "FES pathway" })).toBeChecked();
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.locator(".answer")).toContainText("Falling Behind pathway in 2030");
});

test("a request that cannot run shows why", async ({ page }) => {
  await page.goto("/result?year=2019&services=dc");
  await expect(page.getByRole("alert")).toHaveText("Frequency response needs a year from 2022.");
});

test("explore lists every year and pathway", async ({ page }) => {
  await page.goto("/explore?hours=4&forecast=perfect_foresight");
  const tables = page.locator("table");
  await expect(tables.first().locator("tbody tr")).toHaveCount(9);
  await expect(tables.nth(1).locator("tbody tr")).toHaveCount(12);
  await tables.first().getByRole("link", { name: "Open" }).first().click();
  await expect(page).toHaveURL(/\/result\?.*year=2017.*/);
});

test("compare keeps its choices in the URL", async ({ page }) => {
  await page.goto("/compare?item=gb-2019&item=gb-2022&item=falling_behind_2030&power_mw=5");
  await expect(page.locator(".answer")).toHaveCount(3);
  await expect(page.getByLabel("Prices 2")).toHaveValue("gb-2022");
  await page.getByLabel("Prices 3").selectOption("");
  await page.getByRole("button", { name: "Show" }).click();
  await expect(page.locator(".answer")).toHaveCount(2);
});

test("FES pathways table", async ({ page }) => {
  await page.goto("/scenarios");
  await expect(page.locator("tbody tr")).toHaveCount(12);
  await expect(page.getByText(/NESO Open Data Licence/)).toBeVisible();
});

test("help is reachable from the keyboard", async ({ page }) => {
  await page.goto("/run");
  const tip = page.getByRole("note").first();
  await tip.focus();
  await expect(tip).toBeFocused();
  await expect(tip).toHaveAttribute("data-tip", /forecast|Scenarios/);
});
