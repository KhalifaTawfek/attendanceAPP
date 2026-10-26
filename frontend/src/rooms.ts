// Rooms in the CJ building (UPB FILS): ground floor CJ 01-05, first floor CJ 11-15, second floor CJ 21-25.
export const ROOM_FLOORS: { label: string; rooms: string[] }[] = [0, 1, 2].map((floor) => ({
  label: floor === 0 ? 'Ground floor' : `Floor ${floor}`,
  rooms: [1, 2, 3, 4, 5].map((n) => `CJ ${floor}${n}`),
}))

export const ROOMS = ROOM_FLOORS.flatMap((f) => f.rooms)
