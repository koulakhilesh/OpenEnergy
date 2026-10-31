import { expect, test } from "@playwright/test";

test("home plays a real day and leads to the lab", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Watch a battery trade a real day on Britain's grid." }),
  ).toBeVisible();
  await expect(page.locator(".counter")).toContainText("£");
  await expect(page.getByText(/Ember, European Wholesale Electricity Price Data/)).toBeVisible();
  await page.getByRole("link", { name: "Try your own battery" }).click();
  await expect(page).toHaveURL(/\/lab\?year=2025&day=/);
});

test("battery lab plans a day in the browser and solves the year", async ({ page }) => {
  await page.goto("/lab?year=2025&day=2025-01-21");
  await expect(page.locator(".answer")).toContainText("Tue, 21 January 2025", { timeout: 30_000 });
  await expect(page.locator(".answer")).toContainText("of what perfect foresight allows");
  await expect(page.getByText(/daily plans solved in/)).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "4 h" }).click();
  await expect(page).toHaveURL(/h=4/);
  await expect(page.locator(".answer")).toContainText("1 MW / 4 MWh");
});

test("beat the battery scores a plan", async ({ page }) => {
  await page.goto("/play?d=2024-03-12");
  const cells = page.getByRole("group", { name: "Your plan, hour by hour" }).getByRole("button");
  await expect(cells).toHaveCount(24, { timeout: 30_000 });
  await cells.nth(3).click(); // charge to full
  await cells.nth(18).click(); // full, so the first tap sells
  await expect(cells.nth(18)).toHaveAccessibleName("18:00 sell");
  await page.getByRole("button", { name: "Lock in my plan" }).click();
  await expect(page.locator(".scoreboard")).toContainText("Optimiser, same forecast");
});

test("grid replay finds a week", async ({ page }) => {
  await page.goto("/replay?week=2025-01-18");
  await expect(page.locator(".now-panel")).toContainText("Wind gives", { timeout: 30_000 });
  await page.getByRole("button", { name: "Windiest week" }).click();
  await expect(page).not.toHaveURL(/week=2025-01-18/);
});

test("2035 answers from the saturation study", async ({ page }) => {
  await page.goto("/2035");
  await expect(page.locator(".answer")).toContainText("GW of batteries", { timeout: 30_000 });
  await page.getByRole("button", { name: "Falling Behind" }).click();
  await expect(page.locator(".answer")).toContainText("Falling Behind 2035");
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
