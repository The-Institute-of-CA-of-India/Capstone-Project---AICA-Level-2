const {
  initializeTestEnvironment,
  assertFails,
  assertSucceeds,
} = require("@firebase/rules-unit-testing");
const { test, before, after, beforeEach } = require("node:test");
const fs = require("node:fs");

let testEnv;
const PROJECT_ID = process.env.GCP_PROJECT || "demo-no-project";
const ALICE_UID = "alice_123";
const BOB_UID = "bob_456";

const [emulatorHost, emulatorPortStr] = (process.env.FIRESTORE_EMULATOR_HOST || "127.0.0.1:8085").split(":");
const emulatorPort = parseInt(emulatorPortStr, 10);

before(async () => {
  const rules = fs.readFileSync("./firestore.rules", "utf8");
  testEnv = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    firestore: {
      rules,
      host: emulatorHost,
      port: emulatorPort,
    },
  });
});

after(async () => {
  if (testEnv) {
    await testEnv.cleanup();
  }
});

beforeEach(async () => {
  if (testEnv) {
    await testEnv.clearFirestore();
  }
});

// --- SECURITY BOUNDS TESTS ---

test("Unauthenticated user: cannot read accounts", async () => {
  const unauthDb = testEnv.unauthenticatedContext().firestore();
  await assertFails(unauthDb.collection("users").doc(ALICE_UID).collection("accounts").get());
});

test("Unauthenticated user: cannot write transactions", async () => {
  const unauthDb = testEnv.unauthenticatedContext().firestore();
  await assertFails(
    unauthDb.collection("users").doc(ALICE_UID).collection("transactions").doc("tx1").set({
      userId: ALICE_UID,
      type: "EXPENSE",
      amount: 150.0,
      accountId: "acc1",
      category: "Food",
      createdAt: new Date(),
    })
  );
});

test("Authenticated user: cannot read another user's accounts", async () => {
  await testEnv.withSecurityRulesDisabled(async (context) => {
    await context.firestore().collection("users").doc(BOB_UID).collection("accounts").doc("bob_acc").set({
      userId: BOB_UID,
      name: "Bob Bank",
      type: "BANK",
      balance: 5000,
      createdAt: new Date(),
    });
  });

  const aliceDb = testEnv.authenticatedContext(ALICE_UID).firestore();
  await assertFails(aliceDb.collection("users").doc(BOB_UID).collection("accounts").doc("bob_acc").get());
});

test("Authenticated user: can create, read, update, and delete own account", async () => {
  const aliceDb = testEnv.authenticatedContext(ALICE_UID).firestore();
  const accRef = aliceDb.collection("users").doc(ALICE_UID).collection("accounts").doc("acc_1");

  const now = new Date();
  await assertSucceeds(
    accRef.set({
      userId: ALICE_UID,
      name: "Alice HDFC",
      type: "BANK",
      balance: 25000,
      creditLimit: 0,
      colorHex: "#1E88E5",
      createdAt: now,
    })
  );

  await assertSucceeds(accRef.get());

  await assertSucceeds(
    accRef.update({
      balance: 24000,
    })
  );

  await assertSucceeds(accRef.delete());
});

test("Authenticated user: can create and read valid transaction", async () => {
  const aliceDb = testEnv.authenticatedContext(ALICE_UID).firestore();
  const txRef = aliceDb.collection("users").doc(ALICE_UID).collection("transactions").doc("tx_1");

  await assertSucceeds(
    txRef.set({
      userId: ALICE_UID,
      type: "EXPENSE",
      amount: 450.5,
      accountId: "acc_1",
      category: "Food & Dining",
      note: "Team lunch",
      createdAt: new Date(),
    })
  );

  await assertSucceeds(aliceDb.collection("users").doc(ALICE_UID).collection("transactions").get());
});

test("Authenticated user: cannot spoof userId in transaction", async () => {
  const aliceDb = testEnv.authenticatedContext(ALICE_UID).firestore();
  const txRef = aliceDb.collection("users").doc(ALICE_UID).collection("transactions").doc("tx_spoofed");

  await assertFails(
    txRef.set({
      userId: BOB_UID, // Spoofed!
      type: "EXPENSE",
      amount: 100,
      accountId: "acc_1",
      category: "Transport",
      createdAt: new Date(),
    })
  );
});

test("Authenticated user: can create investment entry", async () => {
  const aliceDb = testEnv.authenticatedContext(ALICE_UID).firestore();
  const invRef = aliceDb.collection("users").doc(ALICE_UID).collection("investments").doc("inv_1");

  await assertSucceeds(
    invRef.set({
      userId: ALICE_UID,
      assetName: "Nifty 50 Index Fund",
      assetType: "MUTUAL_FUNDS",
      action: "CONTRIBUTION",
      amount: 10000,
      note: "Monthly SIP",
      createdAt: new Date(),
    })
  );
});
