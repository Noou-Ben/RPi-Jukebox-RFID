import { useContext, useEffect, useState } from 'react';
import { omit } from 'ramda';
import { useTranslation } from 'react-i18next';

import PubSubContext from '../../context/pubsub/context';
import CardsForm from './form';
import { useLocation } from 'react-router-dom';

const CardsRegister = () => {
  const { t } = useTranslation();
  const {
    state: { 'rfid.card_id': swipedCardId },
    setState
  } = useContext(PubSubContext);
  const { state: locationState } = useLocation();
  const { registerCard } = locationState || {};

  const [cardId, setCardId] = useState(undefined);
  const [actionData, setActionData] = useState(registerCard?.actionData || {});

  useEffect(() => {
    setState(state => (omit(['rfid.card_id'], state)));
  }, [setState]);

  useEffect(() => {
    setCardId(swipedCardId || registerCard?.cardId);
  }, [registerCard, swipedCardId])

  useEffect(() => {
    // actionData is seeded from location state via useState's lazy initializer, which only
    // runs on first mount - if this route is navigated to again while already mounted (e.g.
    // from a dialog that stays on the page, like the Jukebox Hub download), that initial
    // value never updates on its own. Re-sync explicitly whenever fresh state arrives, same
    // as cardId above.
    if (registerCard?.actionData) setActionData(registerCard.actionData);
  }, [registerCard])

  return (
    <CardsForm
      title={t('cards.register.register-card')}
      cardId={cardId}
      actionData={actionData}
      setActionData={setActionData}
    />
  );
};

export default CardsRegister;
