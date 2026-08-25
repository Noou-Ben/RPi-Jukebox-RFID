import SelectTimers from './actions/timers';
import SelectAudio from './actions/audio';
import SelectHost from './actions/host';
import SelectSynchronisation from './actions/synchronisation';

// Renders the command sub-selector for every action type except `play_music`,
// which needs its own library navigation and is handled by callers directly.
const ActionTypeFields = ({
  actionData,
  handleActionDataChange,
}) => (
  <>
    {actionData.action === 'host' &&
      <SelectHost
        actionData={actionData}
        handleActionDataChange={handleActionDataChange}
      />
    }

    {actionData.action === 'timers' &&
      <SelectTimers
        actionData={actionData}
        handleActionDataChange={handleActionDataChange}
      />
    }

    {actionData.action === 'audio' &&
      <SelectAudio
        actionData={actionData}
        handleActionDataChange={handleActionDataChange}
      />
    }

    {actionData.action === 'synchronisation' &&
      <SelectSynchronisation
        actionData={actionData}
        handleActionDataChange={handleActionDataChange}
      />
    }
  </>
);

export default ActionTypeFields;
