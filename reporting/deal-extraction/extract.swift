import Foundation

let inputPath = "/Users/mgottron/.claude/projects/-Users-mgottron-Claude-Code/527ec8aa-2cac-47b3-8bc8-1eefdc3a1687/tool-results/mcp-4015ff8e-8996-4ec0-b434-76a999e3f7b7-search_crm_objects-1770992993243.txt"
let outputPath = "/Users/mgottron/Claude Code/deal_data_batch1.json"

guard let rawData = FileManager.default.contents(atPath: inputPath),
      let wrapper = try? JSONSerialization.jsonObject(with: rawData) as? [[String: Any]],
      let firstItem = wrapper.first,
      let textString = firstItem["text"] as? String,
      let textData = textString.data(using: .utf8),
      let innerData = try? JSONSerialization.jsonObject(with: textData) as? [String: Any] else {
    print("Failed to parse input file")
    exit(1)
}

let totalInPipeline = innerData["total"] as? Int ?? 0
let offset = innerData["offset"] as? Int ?? 0
let results = innerData["results"] as? [[String: Any]] ?? []

var deals: [[String: Any]] = []

for r in results {
    let id = r["id"] as? Int ?? 0
    let props = r["properties"] as? [String: Any] ?? [:]

    let amountStr = props["amount"] as? String ?? ""
    let amount: Double
    if let a = Double(amountStr) {
        amount = a
    } else {
        amount = 0
    }

    let isClosedStr = props["hs_is_closed_count"] as? String ?? "0"
    let isClosed = Int(isClosedStr) ?? 0

    var deal: [String: Any] = [
        "id": String(id),
        "stage": props["dealstage"] as? String ?? "",
        "dealtype": props["dealtype"] as? String ?? "",
        "sub_category": props["deal_type___sub_category"] as? String ?? "",
        "owner_id": props["hubspot_owner_id"] as? String ?? "",
        "amount": amount,
        "createdate": props["createdate"] as? String ?? "",
        "closedate": props["closedate"] as? String ?? "",
        "is_closed": isClosed,
    ]

    let stageFields = [
        "entered_demo_scheduled": "entered_demo_scheduled_stage__historic__date",
        "entered_demo_held": "entered_demo_held_stage__historic__date",
        "entered_agreed_in_principle": "entered_agreed_in_principle_stage__historic__date",
        "entered_closed_won": "entered_closed_won_stage__historic__date",
        "entered_closed_lost": "entered_closed_lost_stage__historic__date"
    ]

    for (key, propKey) in stageFields {
        if let val = props[propKey] as? String {
            deal[key] = val
        } else {
            deal[key] = NSNull()
        }
    }

    deals.append(deal)
}

let output: [String: Any] = [
    "total_deals": deals.count,
    "offset_for_next_page": offset,
    "total_in_pipeline": totalInPipeline,
    "deals": deals
]

if let jsonData = try? JSONSerialization.data(withJSONObject: output, options: [.prettyPrinted, .sortedKeys]),
   let jsonString = String(data: jsonData, encoding: .utf8) {
    try? jsonString.write(toFile: outputPath, atomically: true, encoding: .utf8)
    print("Successfully extracted \(deals.count) deals")
    print("Total in pipeline: \(totalInPipeline)")
    print("Offset for next page: \(offset)")
    print("Output written to: \(outputPath)")

    // Show all unique property keys
    var allKeys = Set<String>()
    for r in results {
        if let props = r["properties"] as? [String: Any] {
            allKeys.formUnion(props.keys)
        }
    }
    print("All unique property keys: \(allKeys.sorted())")
} else {
    print("Failed to serialize output")
    exit(1)
}
