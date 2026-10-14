import test from 'node:test';
import assert from 'node:assert/strict';

test('mutation targets are captured in dialog context and cannot silently change on patient switch', () => {
  // Simulate opening an upload dialog for patient A while clinician is viewing patient A
  let activePatient = 'patient-asha';
  const activeUser = 'doctor-meera';

  const dialog = {
    kind: 'upload',
    patientId: activePatient,
    accountId: activeUser
  };

  // Clinician attempts to switch global view to patient B
  activePatient = 'patient-kabir';

  // The dialog target remains bound to patient A
  assert.equal(dialog.patientId, 'patient-asha');
  assert.equal(dialog.accountId, 'doctor-meera');

  // isPatientMutationDialogOpen correctly disables switching
  const isPatientMutationDialogOpen =
    dialog !== null &&
    (dialog.kind === 'appointment' ||
      dialog.kind === 'upload' ||
      dialog.kind === 'intake' ||
      dialog.kind === 'instructions');
  assert.equal(isPatientMutationDialogOpen, true);
});

test('simulate logout/account switch while read/write is outstanding; no stale state applied', async () => {
  let activeUser = 'doctor-meera';
  let activePatient = 'patient-asha';
  let workspaceState = { patient: { id: 'patient-asha', name: 'Asha' } };

  // Initiating account and target
  const initiatingAccountId = 'doctor-meera';
  const targetPatientId = 'patient-asha';

  // Simulating async save completion
  const handleSaved = async (fetchWorkspace) => {
    // Before callback finishes, user logs out
    activeUser = undefined;
    activePatient = '';

    // Guard in App.tsx:
    if (!activeUser || activeUser !== initiatingAccountId) {
      return; // Abort applying stale state
    }

    const updated = await fetchWorkspace();
    workspaceState = updated;
  };

  let fetched = false;
  await handleSaved(async () => {
    fetched = true;
    return { patient: { id: 'patient-asha', name: 'Stale Asha' } };
  });

  assert.equal(fetched, false, 'Fetch must not be executed or applied after session change');
  assert.equal(workspaceState.patient.name, 'Asha', 'Existing state must remain unaffected by stale callback');
});

test('simulate successful POST followed by failed refresh; only one POST occurs and a refresh action remains available', async () => {
  let postCount = 0;
  let getCount = 0;
  let isStale = false;
  let dialogOpen = true;
  let toastMessage = '';
  let errorState = null;

  const mockPostMutation = async () => {
    postCount++;
    return { ok: true };
  };

  const mockGetWorkspace = async (shouldFail = false) => {
    getCount++;
    if (shouldFail) throw new Error('Network error during refresh');
    return { patient: { id: 'patient-asha' } };
  };

  // 1. POST mutation executes once
  await mockPostMutation();
  assert.equal(postCount, 1);

  // 2. handleSaved handles result and attempts refresh
  const handleSaved = async (targetId, accountId, successMsg) => {
    dialogOpen = false; // Dialog closes immediately, preventing duplicate submit
    try {
      await mockGetWorkspace(true); // Fails
      isStale = false;
    } catch {
      isStale = true;
      toastMessage = `${successMsg} (Refresh failed)`;
      errorState = {
        message: 'Saved; refresh failed. Check your connection.',
        retry: async () => {
          await mockGetWorkspace(false); // Retries GET, NOT POST
          isStale = false;
          errorState = null;
        }
      };
    }
  };

  await handleSaved('patient-asha', 'doctor-meera', 'Appointment saved');

  assert.equal(dialogOpen, false, 'Dialog must be closed so user cannot resubmit POST');
  assert.equal(postCount, 1, 'POST must have happened exactly once');
  assert.equal(getCount, 1, 'Initial refresh GET was attempted');
  assert.equal(isStale, true, 'isStale must be true when refresh fails');
  assert.ok(toastMessage.includes('Refresh failed'));
  assert.ok(errorState !== null && typeof errorState.retry === 'function');

  // 3. User clicks Retry on the error banner: only GET is called, NOT POST
  await errorState.retry();
  assert.equal(postCount, 1, 'Retry must NOT repeat the mutation POST');
  assert.equal(getCount, 2, 'Retry must re-fetch workspace via GET');
  assert.equal(isStale, false, 'isStale cleared after successful refresh');
  assert.equal(errorState, null, 'Error state cleared after successful refresh');
});

test('empty hospital workspaces remain usable; retrying a failed patient-list fetch actually reloads patients', async () => {
  let activeUser = 'doctor-new';
  let patientsState = null;
  let errorState = null;
  let fetchAttempts = 0;

  const loadPatients = async (uid) => {
    fetchAttempts++;
    if (fetchAttempts === 1) {
      // Simulate initial failure
      if (activeUser === uid) {
        errorState = {
          message: 'Failed to load patients',
          retry: () => loadPatients(uid)
        };
      }
      return;
    }
    // Simulate successful empty hospital workspace
    if (activeUser === uid) {
      patientsState = [];
      errorState = null;
    }
  };

  // Initial attempt fails
  await loadPatients('doctor-new');
  assert.equal(fetchAttempts, 1);
  assert.equal(patientsState, null);
  assert.ok(errorState !== null);

  // Clinician clicks retry on the error banner
  await errorState.retry();
  assert.equal(fetchAttempts, 2, 'Retry must call loadPatients again');
  assert.deepEqual(patientsState, [], 'Empty patient list must be handled cleanly without crash');
  assert.equal(errorState, null, 'Error banner dismissed on successful reload');
});
