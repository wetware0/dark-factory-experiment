# filter-incidents

Search for customer incidents using filter criteria.

## When To Use

- Searching for incidents by product, module, or criticality
- Finding incidents with specific status
- Looking for incidents created within a time window
- Getting an overview of recent incidents
- Filtering by reporting organisation code or enterprise code to scope incidents to a specific customer
- Filtering by country/region code to scope incidents to a specific geography

## When Not Use

- Searching incidents by keywords/query text (semantic search). Use the knowledge/documentation MCP server tools for that.

## Input

```yaml
product:
  type: string
  required: true
  description: Product code (e.g., ENT). Use lookup-products() to find valid codes.
area:
  type: string[]
  required: false
  description: Product area code(s). A 3-character code representing a high-level category within a product (e.g. DEL, FIN, OPS).
module:
  type: string[]
  required: false
  description: Module codes array. Use lookup-modules(product: "ENT") to find valid codes.
criticality:
  type: string[]
  required: false
  description: Criticality codes (CR1-CR9).
status:
  type: string[]
  required: false
  description: Status codes (APP, CSV, DEV, CLS, etc.).
reportedOrgCode:
  type: string[]
  required: false
  description: >
    Filter by reporting organisation code(s). The org code identifies the specific
    branch/office/subsidiary within an enterprise that filed the incident (e.g. "DHLGLOBNJ"
    for DHL's New Jersey office). Use when you need incidents from a specific reporting location.
reportedEnterpriseCode:
  type: string[]
  required: false
  description: >
    Filter by enterprise code(s). A 3-character code identifying the top-level CargoWise customer
    enterprise — the company that holds the CargoWise license (e.g. "DFO"). One enterprise
    = one CargoWise tenant and can contain many organisations. Use to scope all incidents from
    one customer regardless of which office filed them.
country:
  type: string[]
  required: false
  description: >
    Filter by country/region code(s). A 2-character ISO country code (e.g. "AU" for Australia,
    "US" for United States, "GB" for United Kingdom). The country field on an incident represents
    the country of the reporting organisation — auto-populated from the logged-on contact's
    organisation address (port country first, main office country as fallback) when the incident
    is created. Use to scope incidents to a specific geographic region.
createdAfter:
  type: string
  required: false
  description: Filter incidents created on or after this ISO date (e.g. 2026-01-01).
createdBefore:
  type: string
  required: false
  description: Filter incidents created on or before this ISO date (e.g. 2026-03-31).
sortBy:
  type: string
  required: false
  description: Sort results by any incident field (e.g. createdAt, updatedAt, status, reportedOrgCode). Default: createdAt (descending).
sortOrder:
  type: string
  required: false
  description: Sort direction when sortBy is specified. Valid values: asc, desc. Default: asc.
skip:
  type: integer
  required: false
  default: 0
  description: Pagination: number of results to skip.
top:
  type: integer
  required: false
  default: 20
  description: Pagination: results per page (max 50).
```

## Output

Returns TOON format with two main sections:

### Main Data: Incidents Array

Array of incident objects containing:

- Number: Incident number (e.g., CS12345678)
- Summary: Incident title/description
- Product: Product code (e.g., ENT)
- Area: Product area code
- Module: Module code (e.g., CUS)
- Criticality: Criticality code (e.g., CR4)
- Status: Status code (e.g., DEV)
- Created: Creation date as an ISO 8601 date string (`YYYY-MM-DD`)
- Updated: Last updated date as an ISO 8601 date string (`YYYY-MM-DD`)
- Reported Enterprise Code: 3-character enterprise code of reporting organisation (e.g., DFO)
- Reported Organisation Code: Short code of the organisation that reported the incident
- Reported Organisation Name: Full name of the organisation that reported the incident
- Reported Staff: Name of the staff contact who reported the incident
- Country: 2-character ISO country code identifying the country of the reporting organisation (e.g. AU, US, GB); null when not set on the incident

### Reference Tables

Lookup tables for code descriptions (only contains values present in the incidents):

- **Criticalities**: Maps criticality codes (CR1-CR9) to descriptions
- **Statuses**: Maps status codes (APP, DEV, etc.) to descriptions
- **Products**: Maps product codes to descriptions
- **Modules**: Maps module codes to descriptions

This structure eliminates redundant inline descriptions and provides efficient lookups for understanding codes.

## Examples

### Usage

```
filter-incidents(product: "ENT")
filter-incidents(product: "ENT", area: ["DEL"])  // Filter by product area
filter-incidents(product: "ENT", criticality: ["CR1", "CR2", "CR3", "CR4"], createdAfter: "2026-01-01") // Find all defects raised since Jan 2026 in ENT product
filter-incidents(product: "ENT", module: ["CUS"], status: ["DEV"], createdAfter: "2026-01-01")
filter-incidents(product: "ENT", reportedOrgCode: ["ABC"])
filter-incidents(product: "ENT", reportedEnterpriseCode: ["WTG"])
filter-incidents(product: "ENT", country: ["AU"])  // Filter by country/region
filter-incidents(product: "ENT", skip: 20, top: 20)  // Page 2
filter-incidents(product: "ENT", sortBy: "updatedAt", sortOrder: "desc")  // Most recently updated first
filter-incidents(product: "ENT", sortBy: "createdAt", sortOrder: "asc")   // Oldest first
```

### Output Example

```
# Found 2 incidents (Index: 1-2)

incidents:
| Number     | Summary              | Product | Area | Module | Criticality | Status | Created    | Updated    | Enterprise Code | Reported Organisation Code | Reported Organisation Name | Reported Staff |
| CS00123456 | Unable to print AWB  | ENT     | DEL  | CUS    | CR4         | DEV    | 2026-01-15 | 2026-01-20 | WTG             | ABC                        | ABC Company Ltd            | John Smith     |
| CS00123457 | Error in customs     | ENT     | DEL  | CUS    | CR3         | CSV    | 2026-01-18 | 2026-01-18 | WTG             | XYZ                        | XYZ Corp                   | Jane Doe       |

Criticalities:
| Code | Description                                       |
| CR3  | Single function not working (No manual work around) |
| CR4  | Single function not working (With manual work around) |

Statuses:
| Code | Description             |
| CSV  | Customer Service Actioning |
| DEV  | Development Team Actioning |

Products:
| Code | Description        |
| ENT  | CargoWise Enterprise |

Modules:
| Code | Description |
| CUS  | Customs     |
```

## References

### Criticality Codes

- `CR1`: Entire system down (System failure)
- `CR2`: Entire module not working (No workaround)
- `CR3`: Single function not working (No workaround)
- `CR4`: Single function not working (With workaround)
- `CR5`: Training Questions
- `CR6`: Feature Request
- `CR7`: Estimate / Quote Request
- `CR8`: Compliance, Reference and Master Data
- `CR9`: Service Request

### Status Codes

- `APP`: Approved and Sent to CargoWise
- `APR`: Request Approval
- `CSV`: Customer Service Actioning
- `DEV`: Development Team Actioning
- `FTR`: Pending Feature Result / Future Release
- `FRA`: Feature Request Accepted
- `DER`: Development Estimate Requested
- `DEP`: Development Estimate Provided
- `FQR`: Formal Quotation Requested
- `FQP`: Formal Quotation Provided
- `FQA`: Formal Quotation Accepted
- `FQD`: Formal Quotation Declined
- `CWR`: Closed - Waiting for Customer Response
- `CLS`: Closed
- `NAP`: Not Approved

## Tips

- Always start with a product filter (required)
- Use `lookup-products()` first if product code is unknown
- Use `lookup-modules(product: "ENT")` to find module codes
- **Enterprise code vs org code**: An enterprise is the top-level CargoWise customer (3-char code, e.g. `DHL`); an organisation is a specific branch/office within that enterprise (e.g. `DHLGLOBNJ`). Use `reportedEnterpriseCode` to see all incidents from one customer enterprise; use `reportedOrgCode` to narrow to a specific reporting office.
- Pagination note appears when more results are available
- `Created` and `Updated` in the output are ISO 8601 date strings (`YYYY-MM-DD`)
- Use scrolling to fetch all results asked by the user
- If the result contains hundreds of incidents, stop and ask the user to refine the criteria
