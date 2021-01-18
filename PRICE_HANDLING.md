# Price handling

Prices from exchanges are sometimes cached. On the other hand it is not a 
good strategy to report old prices. Our system also needs to be able to 
validate prices from some recent past.

Keeping all this in mind we implemented what's explained below.

## Price retrieval 

When a price is received it is inserted in our price queue. If the 
price-information includes a timestamp from when it was originated, it is
recorded. Otherwise we record the reception time as the price timestamp.
If we receive an "age" header, system uses it to adjust the price timestamp.
As we don't want to populate queue with old prices, when the price has a 
timestamp older than `ORACLE_PRICE_RECEIVE_MAX_AGE` seconds it will not be 
saved as received. We will save a Not-A-Price price instead with the current
timestamp. (We use a decimal NaN to signal the Not-A-Price value).

## Price publication and validation

When a price is generated, the price is created according to the nearest 
price in each exchange queue for the current time.

When a price related to a timestamp is to be validated, it is compared 
against the price we can generate from our exchanges' queues for the mentioned
timestamp.

In both cases, the price selection for each queue will be done in the 
following way:
 * We select the price with nearest time (including NANs):
    + If there is more than one, the most recent one will be choosen
 * If a queue is empty, it will be ignored
 * If a price queue has NAN it will be ignored
 * When the price is for publishing, if the price is older than: 
    `ORACLE_PRICE_PUBLISH_MAX_DIFF` it is ignored
 * When the price is for validation, if the price is older than:
    `ORACLE_PRICE_VALIDATE_MAX_DIFF` it is ignored
 * If there is no price: no price is returned
 * Remaining prices are weighted by a normalized factor which can be
 configured. When one of the sources needs to be ignored, the factor will 
 get re-normalized only using the active sources.
