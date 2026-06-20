- **CQ1**
```sparql
PREFIX defi: <http://defisocialonto.org/defisocialonto#>

SELECT
  ?linguisticVariant
  ?variantText
  (GROUP_CONCAT(DISTINCT ?conceptName; separator="; ") AS ?expressedConcepts)
  (COUNT(DISTINCT ?discourseUnit) AS ?frequency)
WHERE {
  ?discourseUnit a defi:DiscourseUnit ;
                 defi:contains ?linguisticVariant .

  ?linguisticVariant a defi:LinguisticVariant ;
                     defi:rawText ?variantText ;
                     defi:expresses ?concept .

  ?concept a defi:Concept ;
           defi:name ?conceptName .
}
GROUP BY ?linguisticVariant ?variantText
ORDER BY DESC(?frequency)
LIMIT 5
```

- **CQ2**
```sparql
PREFIX defi: <http://defisocialonto.org/defisocialonto#>

SELECT
  ?risk
  ?riskName
  ?riskDescription
  (GROUP_CONCAT(DISTINCT ?conceptName; separator="; ") AS ?associatedConcepts)
  (GROUP_CONCAT(DISTINCT ?variantText; separator="; ") AS ?associatedLinguisticVariants)
  (COUNT(DISTINCT ?discourseUnit) AS ?frequency)
WHERE {
  ?discourseUnit a defi:DiscourseUnit ;
                 defi:contains ?linguisticVariant .

  ?linguisticVariant a defi:LinguisticVariant ;
                     defi:rawText ?variantText ;
                     defi:expresses ?concept .

  ?concept a defi:Concept ;
           defi:name ?conceptName ;
           defi:isAssociatedWith ?risk .

  ?risk a defi:Risk ;
        defi:name ?riskName ;
        defi:description ?riskDescription .
}
GROUP BY ?risk ?riskName ?riskDescription
ORDER BY DESC(?frequency)
LIMIT 5
```

- **CQ3**
```sparql
PREFIX defi: <http://defisocialonto.org/defisocialonto#>

SELECT
  ?measure
  ?measureName
  ?measureDescription
  (GROUP_CONCAT(DISTINCT CONCAT(STR(?principleNumber), ". ", ?principleDescription); separator="; ") AS ?consumerProtectionPrinciples)
  (COUNT(DISTINCT ?risk) AS ?numberOfLinkedRisks)
WHERE {
  ?measure a defi:ConsumerProtectionMeasure ;
           defi:name ?measureName ;
           defi:description ?measureDescription .

  OPTIONAL {
    ?measure defi:isCoveredBy ?principle .

    ?principle a defi:ConsumerProtectionPrinciple ;
               defi:number ?principleNumber ;
               defi:description ?principleDescription .
  }

  OPTIONAL {
    ?risk a defi:Risk ;
          defi:isAddressedBy ?measure .
  }
}
GROUP BY ?measure ?measureName ?measureDescription
ORDER BY DESC(?numberOfLinkedRisks) ?measureName
```

- **CQ4**
```sparql
PREFIX defi: <http://defisocialonto.org/defisocialonto#>

SELECT
  ?foresightName
  ?foresightDescription
  (GROUP_CONCAT(DISTINCT ?riskName; separator="; ") AS ?associatedRisks)
  (GROUP_CONCAT(DISTINCT ?variantText; separator="; ") AS ?associatedLinguisticVariants)
  (COUNT(DISTINCT ?discourseUnit) AS ?numberOfDiscourseUnits)
WHERE {
  ?discourseUnit a defi:DiscourseUnit ;
                 defi:contains ?linguisticVariant .

  ?linguisticVariant a defi:LinguisticVariant ;
                     defi:rawText ?variantText ;
                     defi:expresses ?concept .

  ?concept defi:isAssociatedWith ?risk .

  ?risk a defi:Risk ;
        defi:name ?riskName ;
        defi:signals ?foresight .

  ?foresight a defi:ActionableForesight ;
             defi:name ?foresightName ;
             defi:description ?foresightDescription .
}
GROUP BY ?foresightName ?foresightDescription
ORDER BY DESC(?numberOfDiscourseUnits) ?foresightName
```
