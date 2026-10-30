import { expect, test } from "@playwright/test";

test("home form runs a precomputed battery and answers first", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "OpenEnergy battery value" })).toBeVisible();
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
  await page.goto("/");
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
  await page.goto("/");
  const tip = page.getByRole("note").first();
  await tip.focus();
  await expect(tip).toBeFocused();
  await expect(tip).toHaveAttribute("data-tip", /forecast|Scenarios/);
});
