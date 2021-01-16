# Price handling

Prices from exchanges are sometimes cached. On the other hand it is not a 
good strategy to report old prices. At the same time we should be able to 
validate prices from some recent past.

We implemented this:

## Price retrieval 

When a price is received it is inserted in our price queue. The reception 
time is record unless the price-information includes a timestamp from when 
it was originated. In the first case, if we receive an "age" header it is 
used to adjust the price timestamp.
As we don't want to populate queue with old prices, when the price have a 
timestamp older than `ORACLE_PRICE_RECEIVE_MAX_AGE` seconds it will not be 
saved as received but a Not-A-Price price with the current timestamp is 
record instead. (We use a decimal NaN to signal the Not-A-Price value).

## Price publication and validation

When a price is generated, the price is created according to the nearest 
price in each exchange queue for the current time.

When a price related to a timestamp is to be validated, it is compared 
against the price we can generate from our exchanges' queues for the mentioned
timestamp.

In both cases, the price selection for each queue is this way:
 * we select the price with nearest time (including NANs):
    + if there is more than once, the newer is choose
 * if a queue is empty it is ignored
 * if a queue price is NAP it is ignored
 * When the price is for publishing if the price is older than: 
    `ORACLE_PRICE_PUBLISH_MAX_DIFF` it is ignored
 * When the price is for validation if the price is older than:
    `ORACLE_PRICE_VALIDATE_MAX_DIFF` it is ignored
 * if there is no price: no price is returned
 * remaining prices are ponderated according to their weights, which are 
   normalized



