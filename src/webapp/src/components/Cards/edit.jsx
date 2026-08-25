import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import request from '../../utils/request';
import CardsForm from './form';
import {
  buildActionData,
  findActionByCommand,
} from './utils';

const CardsEdit = () => {
  const { t } = useTranslation();
  const { cardId } = useParams();
  const [actionData, setActionData] = useState({});

  useEffect(() => {
    const loadCardList = async () => {
      if (cardId) {
        const { result, error } = await request('cardsList');

        if (result && result[cardId]) {
          const {
            action: { args, post_actions = [] },
            from_alias: command
          } = result[cardId];

          const action = findActionByCommand(command);
          const postActions = post_actions.map(({ from_alias, args }) => {
            const postAction = findActionByCommand(from_alias);
            return buildActionData(postAction, from_alias, args || []);
          });
          const actionData = buildActionData(action, command, args, { postActions });

          setActionData(actionData);
        }

        if (error) {
          console.error(error);
        }
      }
    }

    loadCardList();
  }, [cardId]);

  return (
    <CardsForm
      title={t('cards.edit.edit-card')}
      cardId={cardId}
      actionData={actionData}
      setActionData={setActionData}
    />
  );
};

export default CardsEdit;
