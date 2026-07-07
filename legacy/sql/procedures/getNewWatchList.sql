-- SqlProcedure: [dbo].[getNewWatchList]

set nocount on

	declare @startdate datetime
	select @startdate = AtWhenSubscribe
	from Member where MemberID=@MemberID

	if @startdate < @atwhen
		begin
			select s.stockID, s.ticker, s.companyname, Round(Convert(money,sd.price * 1.10),2) as BuyTarget
			from stock s			
			inner join newdwap nd on nd.stockID=s.stockID
			inner join stockdata sd on s.stockID=sd.stockID and sd.atwhen=nd.atwhen			
			where nd.atwhen = @atwhen			
			order by s.companyname
		end
	else
		begin
			select null as StockID, '' as Ticker,'' as CompanyName, 0 as BuyTarget
		end
set nocount off
