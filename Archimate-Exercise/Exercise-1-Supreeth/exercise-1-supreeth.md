## Buying Coffee with a Contactless Card at a Cafe
 
This model describes the process of purchasing coffee at a cafe using a contactless payment card. The customer interacts with the barista to place an order and make payment. The main business process is “Take Payment,” which includes validating and completing the payment transaction. Once payment is approved, the process triggers the preparation of the coffee.
 
The cafe uses a POS Application to process card payments. The POS Application provides the Payment Processing Service, which supports the business payment process. Payment transaction information is stored as a Payment Transaction data object and sent to an external Payment Gateway System for authorization.
 
At the technology layer, the payment process is supported by a Card Reader connected to the Cafe POS Terminal. These devices communicate securely with the external Payment Network Server through the Secure Payment Communication technology service. The layered model demonstrates how business activities depend on application services and underlying technology infrastructure to complete a successful coffee purchase.